import asyncio
import websockets
import json
import random
import time
from typing import Dict, List, Tuple
from enum import Enum
import uuid


class Direction(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)


class PlayerColors:
    COLORS = [
        {"head": (76, 175, 80), "body": (139, 195, 74), "name": "绿色"},  # 绿色
        {"head": (244, 67, 54), "body": (255, 138, 128), "name": "红色"},  # 红色
        {"head": (33, 150, 243), "body": (100, 181, 246), "name": "蓝色"},  # 蓝色
        {"head": (255, 193, 7), "body": (255, 224, 130), "name": "黄色"},  # 黄色
        {"head": (156, 39, 176), "body": (186, 104, 200), "name": "紫色"},  # 紫色
    ]


class Snake:
    def __init__(self, player_id: str, start_pos: Tuple[int, int], color_index: int):
        self.player_id = player_id
        self.body = [start_pos, (start_pos[0] - 1, start_pos[1]), (start_pos[0] - 2, start_pos[1])]
        self.direction = Direction.RIGHT
        self.grow_pending = False
        self.color_index = color_index
        self.alive = True
        self.score = 0

    def move(self):
        if not self.alive:
            return

        head = self.body[0]
        new_head = (
            head[0] + self.direction.value[0],
            head[1] + self.direction.value[1]
        )
        self.body.insert(0, new_head)

        if not self.grow_pending:
            self.body.pop()
        else:
            self.grow_pending = False

    def change_direction(self, new_direction: Direction):
        if not self.alive:
            return

        # 防止反向移动
        opposite_directions = {
            Direction.UP: Direction.DOWN,
            Direction.DOWN: Direction.UP,
            Direction.LEFT: Direction.RIGHT,
            Direction.RIGHT: Direction.LEFT
        }
        if new_direction != opposite_directions.get(self.direction):
            self.direction = new_direction

    def grow(self):
        self.grow_pending = True
        self.score += 10

    def check_wall_collision(self, grid_width: int, grid_height: int) -> bool:
        if not self.alive:
            return False

        head = self.body[0]
        return (head[0] < 0 or head[0] >= grid_width or
                head[1] < 0 or head[1] >= grid_height)

    def check_self_collision(self) -> bool:
        if not self.alive:
            return False

        head = self.body[0]
        return head in self.body[1:]

    def check_snake_collision(self, other_snake) -> bool:
        if not self.alive or not other_snake.alive:
            return False

        head = self.body[0]
        return head in other_snake.body


class Food:
    def __init__(self, position: Tuple[int, int]):
        self.position = position


class GameServer:
    def __init__(self):
        self.GRID_WIDTH = 50  # 扩大游戏区域
        self.GRID_HEIGHT = 35
        self.MAX_PLAYERS = 5
        self.GAME_SPEED = 10  # 游戏更新频率 (FPS)

        self.players: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.snakes: Dict[str, Snake] = {}
        self.foods: List[Food] = []
        self.game_running = False
        self.last_update = time.time()

        # 生成初始食物
        self.generate_foods(8)  # 增加食物数量

    def generate_start_positions(self) -> List[Tuple[int, int]]:
        """为玩家生成不重叠的起始位置"""
        positions = [
            (10, 10),  # 左上
            (40, 10),  # 右上
            (10, 25),  # 左下
            (40, 25),  # 右下
            (25, 17),  # 中心
        ]
        return positions

    def generate_foods(self, count: int):
        """生成食物，避免与蛇身重叠"""
        occupied_positions = set()
        for snake in self.snakes.values():
            occupied_positions.update(snake.body)

        for food in self.foods:
            occupied_positions.add(food.position)

        while len(self.foods) < count:
            pos = (random.randint(0, self.GRID_WIDTH - 1),
                   random.randint(0, self.GRID_HEIGHT - 1))
            if pos not in occupied_positions:
                self.foods.append(Food(pos))
                occupied_positions.add(pos)

    async def register_player(self, websocket):
        """注册新玩家"""
        if len(self.players) >= self.MAX_PLAYERS:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "游戏房间已满，最多支持5人同时游戏"
            }))
            await websocket.close()
            return

        player_id = str(uuid.uuid4())
        self.players[player_id] = websocket

        # 创建蛇
        start_positions = self.generate_start_positions()
        color_index = len(self.snakes)
        start_pos = start_positions[color_index] if color_index < len(start_positions) else (25, 17)

        snake = Snake(player_id, start_pos, color_index)
        self.snakes[player_id] = snake

        print(f"玩家 {player_id[:8]} 加入游戏，当前玩家数: {len(self.players)}")

        # 发送欢迎消息
        await websocket.send(json.dumps({
            "type": "welcome",
            "player_id": player_id,
            "color": PlayerColors.COLORS[color_index],
            "message": f"欢迎加入游戏！你是{PlayerColors.COLORS[color_index]['name']}蛇"
        }))

        # 开始游戏循环（如果还没开始）
        if not self.game_running:
            self.game_running = True
            asyncio.create_task(self.game_loop())

        # 广播玩家加入消息
        await self.broadcast_game_state()

        try:
            async for message in websocket:
                await self.handle_message(player_id, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister_player(player_id)

    async def unregister_player(self, player_id: str):
        """注销玩家"""
        if player_id in self.players:
            del self.players[player_id]
        if player_id in self.snakes:
            del self.snakes[player_id]

        print(f"玩家 {player_id[:8]} 离开游戏，当前玩家数: {len(self.players)}")

        # 如果没有玩家了，停止游戏循环
        if len(self.players) == 0:
            self.game_running = False

        # 广播更新
        await self.broadcast_game_state()

    async def handle_message(self, player_id: str, message: str):
        """处理玩家消息"""
        try:
            data = json.loads(message)

            if data["type"] == "direction":
                direction_map = {
                    "UP": Direction.UP,
                    "DOWN": Direction.DOWN,
                    "LEFT": Direction.LEFT,
                    "RIGHT": Direction.RIGHT
                }

                if data["direction"] in direction_map and player_id in self.snakes:
                    self.snakes[player_id].change_direction(direction_map[data["direction"]])

        except json.JSONDecodeError:
            print(f"收到无效消息: {message}")

    async def game_loop(self):
        """主游戏循环"""
        while self.game_running and len(self.players) > 0:
            current_time = time.time()
            if current_time - self.last_update >= 1.0 / self.GAME_SPEED:
                self.update_game()
                await self.broadcast_game_state()
                self.last_update = current_time

            await asyncio.sleep(0.01)  # 避免CPU占用过高

    def update_game(self):
        """更新游戏状态"""
        # 移动所有活着的蛇
        for snake in self.snakes.values():
            if snake.alive:
                snake.move()

        # 检查碰撞
        for player_id, snake in self.snakes.items():
            if not snake.alive:
                continue

            # 检查墙壁碰撞
            if snake.check_wall_collision(self.GRID_WIDTH, self.GRID_HEIGHT):
                snake.alive = False
                print(f"玩家 {player_id[:8]} 撞墙死亡")
                continue

            # 检查自身碰撞
            if snake.check_self_collision():
                snake.alive = False
                print(f"玩家 {player_id[:8]} 撞到自己死亡")
                continue

            # 检查与其他蛇的碰撞
            for other_id, other_snake in self.snakes.items():
                if other_id != player_id and snake.check_snake_collision(other_snake):
                    snake.alive = False
                    print(f"玩家 {player_id[:8]} 撞到其他蛇死亡")
                    break

        # 检查食物碰撞
        for snake in self.snakes.values():
            if not snake.alive:
                continue

            head = snake.body[0]
            for food in self.foods[:]:  # 使用切片避免修改列表时出错
                if head == food.position:
                    snake.grow()
                    self.foods.remove(food)
                    print(f"玩家 {snake.player_id[:8]} 吃到食物，得分: {snake.score}")
                    break

        # 保持食物数量
        self.generate_foods(8)

        # 检查是否需要重置死亡的蛇
        self.respawn_dead_snakes()

    def respawn_dead_snakes(self):
        """重生死亡的蛇（5秒后）"""
        start_positions = self.generate_start_positions()

        for player_id, snake in self.snakes.items():
            if not snake.alive:
                # 简单重生逻辑：立即重生到起始位置
                color_index = snake.color_index
                start_pos = start_positions[color_index] if color_index < len(start_positions) else (25, 17)

                # 检查起始位置是否安全
                occupied = False
                for other_snake in self.snakes.values():
                    if other_snake.alive and start_pos in other_snake.body:
                        occupied = True
                        break

                if not occupied:
                    snake.body = [start_pos, (start_pos[0] - 1, start_pos[1]), (start_pos[0] - 2, start_pos[1])]
                    snake.direction = Direction.RIGHT
                    snake.alive = True
                    snake.score = 0
                    print(f"玩家 {player_id[:8]} 重生")

    async def broadcast_game_state(self):
        """广播游戏状态给所有玩家"""
        if not self.players:
            return

        # 构建游戏状态
        game_state = {
            "type": "game_state",
            "snakes": {},
            "foods": [{"position": food.position} for food in self.foods],
            "grid_size": {"width": self.GRID_WIDTH, "height": self.GRID_HEIGHT},
            "colors": PlayerColors.COLORS
        }

        for player_id, snake in self.snakes.items():
            game_state["snakes"][player_id] = {
                "body": snake.body,
                "alive": snake.alive,
                "score": snake.score,
                "color_index": snake.color_index
            }

        message = json.dumps(game_state)

        # 发送给所有连接的玩家
        disconnected_players = []
        for player_id, websocket in self.players.items():
            try:
                await websocket.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected_players.append(player_id)

        # 清理断开连接的玩家
        for player_id in disconnected_players:
            await self.unregister_player(player_id)


async def main():
    print("* 多人贪吃蛇游戏服务器启动中...")
    print("服务器地址: ws://localhost:8765")
    print("最大玩家数: 5")
    print("游戏区域: 50x35")

    game_server = GameServer()

    async with websockets.serve(game_server.register_player, "localhost", 8765):
        print("* 服务器已启动，等待玩家连接...")
        await asyncio.Future()  # 保持服务器运行


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n* 服务器已关闭")
