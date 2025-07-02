import pygame
import asyncio
import websockets
import json
import queue
import time
from enum import Enum

# 初始化pygame
pygame.init()


class Direction(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)


class Colors:
    # 配色方案
    BACKGROUND = (15, 15, 35)
    GRADIENT_START = (25, 25, 55)
    GRADIENT_END = (15, 15, 35)
    TEXT_PRIMARY = (255, 255, 255)
    TEXT_SECONDARY = (189, 189, 189)
    GRID_LINE = (40, 40, 70)
    SHADOW = (0, 0, 0, 50)
    FOOD = (255, 215, 0)
    FOOD_GLOW = (255, 255, 128)


def get_chinese_font(size):
    """获取支持中文的字体"""
    import platform
    import os

    system = platform.system()
    chinese_fonts = []

    if system == "Windows":
        chinese_fonts = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
        ]
    elif system == "Darwin":  # macOS
        chinese_fonts = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
        ]
    else:  # Linux
        chinese_fonts = [
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        ]

    for font_path in chinese_fonts:
        try:
            if os.path.exists(font_path):
                return pygame.font.Font(font_path, size)
        except:
            continue

    try:
        return pygame.font.Font(None, size)
    except:
        return pygame.font.Font(None, size)


class SnakeClient:
    def __init__(self):
        # 初始窗口尺寸（可调整）
        self.WINDOW_WIDTH = 1400
        self.WINDOW_HEIGHT = 900
        self.MIN_WIDTH = 800
        self.MIN_HEIGHT = 600
        self.GRID_SIZE = 20

        # 创建可调整大小的窗口
        self.screen = pygame.display.set_mode((self.WINDOW_WIDTH, self.WINDOW_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("贪吃蛇Online - Snake Game Online")

        self.clock = pygame.time.Clock()
        self.font_large = get_chinese_font(36)
        self.font_medium = get_chinese_font(24)
        self.font_small = get_chinese_font(18)

        # 网络相关
        self.websocket = None
        self.connected = False
        self.player_id = None
        self.message_queue = queue.Queue()
        self.pending_connection = False
        self.connection_task = None

        # 游戏状态
        self.game_state = None
        self.my_color = None
        self.grid_width = 50
        self.grid_height = 35
        self.colors = []

        # 计算初始游戏区域偏移
        self.update_game_layout()

        # 连接状态
        self.connection_status = "未连接"
        self.last_ping = time.time()

        # 调试信息
        self.debug_info = []

    def add_debug_info(self, message):
        """添加调试信息"""
        timestamp = time.strftime("%H:%M:%S")
        self.debug_info.append(f"[{timestamp}] {message}")
        if len(self.debug_info) > 10:  # 只保留最近10条
            self.debug_info.pop(0)
        print(f"* {message}")

    def update_game_layout(self):
        """更新游戏布局以适应窗口大小"""
        # 确保游戏区域能够适应窗口
        max_game_width = self.WINDOW_WIDTH - 100  # 留出边距
        max_game_height = self.WINDOW_HEIGHT - 150  # 留出UI空间

        # 计算合适的网格大小
        grid_size_by_width = max_game_width // self.grid_width
        grid_size_by_height = max_game_height // self.grid_height
        self.GRID_SIZE = min(grid_size_by_width, grid_size_by_height, 25)  # 最大25像素
        self.GRID_SIZE = max(self.GRID_SIZE, 10)  # 最小10像素

        # 游戏区域偏移（居中显示）
        game_area_width = self.grid_width * self.GRID_SIZE
        game_area_height = self.grid_height * self.GRID_SIZE

        self.game_offset_x = (self.WINDOW_WIDTH - game_area_width) // 2
        self.game_offset_y = (self.WINDOW_HEIGHT - game_area_height) // 2 + 30

        # 确保游戏区域不会超出窗口
        self.game_offset_x = max(50, self.game_offset_x)
        self.game_offset_y = max(80, self.game_offset_y)

    async def connect_to_server(self):
        """连接到游戏服务器"""
        self.add_debug_info("connect_to_server 方法开始执行")

        if self.pending_connection:
            self.add_debug_info("已有连接正在进行中，跳过")
            return

        self.pending_connection = True
        try:
            self.connection_status = "连接中..."
            self.add_debug_info("开始连接到 ws://localhost:8765")

            # 添加连接超时
            self.websocket = await asyncio.wait_for(
                websockets.connect("ws://localhost:8765"),
                timeout=10.0
            )

            self.connected = True
            self.connection_status = "已连接"
            self.add_debug_info("* 成功连接到游戏服务器")

            # 启动消息接收循环
            await self.receive_messages()

        except asyncio.TimeoutError:
            self.connection_status = "连接超时"
            self.add_debug_info("* 连接超时")
            self.connected = False
        except ConnectionRefusedError:
            self.connection_status = "服务器拒绝连接"
            self.add_debug_info("* 服务器拒绝连接，请确保服务器已启动")
            self.connected = False
        except Exception as e:
            self.connection_status = f"连接失败: {str(e)}"
            self.add_debug_info(f"* 连接失败: {e}")
            self.connected = False
        finally:
            self.pending_connection = False
            self.add_debug_info("connect_to_server 方法执行完毕")

    async def receive_messages(self):
        """接收服务器消息"""
        self.add_debug_info("开始接收服务器消息")
        try:
            async for message in self.websocket:
                data = json.loads(message)
                self.message_queue.put(data)
                self.last_ping = time.time()
        except websockets.exceptions.ConnectionClosed:
            self.add_debug_info("* 与服务器的连接已断开")
            self.connected = False
            self.connection_status = "连接断开"
        except Exception as e:
            self.add_debug_info(f"* 接收消息时出错: {e}")
            self.connected = False
            self.connection_status = f"错误: {str(e)}"

    async def send_direction(self, direction: str):
        """发送方向指令到服务器"""
        if self.connected and self.websocket:
            try:
                message = json.dumps({
                    "type": "direction",
                    "direction": direction
                })
                await self.websocket.send(message)
            except Exception as e:
                self.add_debug_info(f"* 发送方向指令失败: {e}")

    def process_messages(self):
        """处理接收到的消息"""
        while not self.message_queue.empty():
            try:
                data = self.message_queue.get_nowait()

                if data["type"] == "welcome":
                    self.player_id = data["player_id"]
                    self.my_color = data["color"]
                    self.add_debug_info(f"* {data['message']}")

                elif data["type"] == "game_state":
                    self.game_state = data
                    self.grid_width = data["grid_size"]["width"]
                    self.grid_height = data["grid_size"]["height"]
                    self.colors = data["colors"]

                    # 重新计算游戏区域布局
                    self.update_game_layout()

                elif data["type"] == "error":
                    self.add_debug_info(f"* 服务器错误: {data['message']}")
                    self.connection_status = data["message"]

            except queue.Empty:
                break
            except Exception as e:
                self.add_debug_info(f"* 处理消息时出错: {e}")

    def draw_gradient_background(self):
        """绘制渐变背景"""
        for y in range(self.WINDOW_HEIGHT):
            ratio = y / self.WINDOW_HEIGHT
            r = int(Colors.GRADIENT_START[0] * (1 - ratio) + Colors.GRADIENT_END[0] * ratio)
            g = int(Colors.GRADIENT_START[1] * (1 - ratio) + Colors.GRADIENT_END[1] * ratio)
            b = int(Colors.GRADIENT_START[2] * (1 - ratio) + Colors.GRADIENT_END[2] * ratio)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (self.WINDOW_WIDTH, y))

    def draw_rounded_rect(self, surface, color, rect, radius):
        """绘制圆角矩形"""
        pygame.draw.rect(surface, color, rect, border_radius=radius)

    def draw_game_grid(self):
        """绘制游戏网格"""
        # 绘制游戏区域背景
        game_rect = pygame.Rect(
            self.game_offset_x - 10,
            self.game_offset_y - 10,
            self.grid_width * self.GRID_SIZE + 20,
            self.grid_height * self.GRID_SIZE + 20
        )
        self.draw_rounded_rect(self.screen, (25, 25, 45), game_rect, 15)

        # 只在网格大小足够大时绘制网格线
        if self.GRID_SIZE >= 15:
            for x in range(self.grid_width + 1):
                start_pos = (self.game_offset_x + x * self.GRID_SIZE, self.game_offset_y)
                end_pos = (self.game_offset_x + x * self.GRID_SIZE, self.game_offset_y + self.grid_height * self.GRID_SIZE)
                pygame.draw.line(self.screen, Colors.GRID_LINE, start_pos, end_pos, 1)

            for y in range(self.grid_height + 1):
                start_pos = (self.game_offset_x, self.game_offset_y + y * self.GRID_SIZE)
                end_pos = (self.game_offset_x + self.grid_width * self.GRID_SIZE, self.game_offset_y + y * self.GRID_SIZE)
                pygame.draw.line(self.screen, Colors.GRID_LINE, start_pos, end_pos, 1)

    def draw_snakes(self):
        """绘制所有蛇"""
        if not self.game_state or "snakes" not in self.game_state:
            return

        for player_id, snake_data in self.game_state["snakes"].items():
            if not snake_data["alive"]:
                continue

            color_index = snake_data["color_index"]
            if color_index >= len(self.colors):
                continue

            color_info = self.colors[color_index]
            head_color = color_info["head"]
            body_color = color_info["body"]

            # 绘制蛇身
            for i, segment in enumerate(snake_data["body"]):
                x = self.game_offset_x + segment[0] * self.GRID_SIZE
                y = self.game_offset_y + segment[1] * self.GRID_SIZE

                if i == 0:  # 蛇头
                    head_rect = pygame.Rect(x + 2, y + 2, self.GRID_SIZE - 4, self.GRID_SIZE - 4)
                    self.draw_rounded_rect(self.screen, head_color, head_rect, max(4, self.GRID_SIZE // 4))

                    # 只在网格足够大时绘制眼睛
                    if self.GRID_SIZE >= 12:
                        eye_size = max(1, self.GRID_SIZE // 8)
                        eye1_pos = (x + self.GRID_SIZE // 4, y + self.GRID_SIZE // 4)
                        eye2_pos = (x + 3 * self.GRID_SIZE // 4, y + self.GRID_SIZE // 4)
                        pygame.draw.circle(self.screen, Colors.TEXT_PRIMARY, eye1_pos, eye_size)
                        pygame.draw.circle(self.screen, Colors.TEXT_PRIMARY, eye2_pos, eye_size)

                    # 如果是自己的蛇，添加特殊标识
                    if player_id == self.player_id:
                        pygame.draw.rect(self.screen, Colors.TEXT_PRIMARY,
                                         pygame.Rect(x, y, self.GRID_SIZE, max(2, self.GRID_SIZE // 8)))
                else:  # 蛇身
                    body_rect = pygame.Rect(x + 3, y + 3, self.GRID_SIZE - 6, self.GRID_SIZE - 6)
                    self.draw_rounded_rect(self.screen, body_color, body_rect, max(3, self.GRID_SIZE // 6))

    def draw_foods(self):
        """绘制食物"""
        if not self.game_state or "foods" not in self.game_state:
            return

        for food in self.game_state["foods"]:
            x = self.game_offset_x + food["position"][0] * self.GRID_SIZE
            y = self.game_offset_y + food["position"][1] * self.GRID_SIZE

            # 绘制发光效果（只在网格足够大时）
            if self.GRID_SIZE >= 15:
                glow_surface = pygame.Surface((self.GRID_SIZE + 6, self.GRID_SIZE + 6), pygame.SRCALPHA)
                pygame.draw.circle(glow_surface, (*Colors.FOOD_GLOW, 30),
                                   (glow_surface.get_width() // 2, glow_surface.get_height() // 2),
                                   glow_surface.get_width() // 2)
                self.screen.blit(glow_surface, (x - 3, y - 3))

            # 绘制食物
            food_center = (x + self.GRID_SIZE // 2, y + self.GRID_SIZE // 2)
            food_radius = max(3, (self.GRID_SIZE - 6) // 2)
            pygame.draw.circle(self.screen, Colors.FOOD, food_center, food_radius)

    def draw_debug_info(self):
        """绘制调试信息"""
        if not self.debug_info:
            return

        debug_y = self.WINDOW_HEIGHT - len(self.debug_info) * 20 - 150
        for i, info in enumerate(self.debug_info):
            debug_text = self.font_small.render(info, True, Colors.TEXT_SECONDARY)
            self.screen.blit(debug_text, (20, debug_y + i * 20))

    def draw_ui(self):
        """绘制用户界面"""
        # 左侧信息面板
        info_x = 20
        info_y = 20
        line_height = 25

        # 连接状态
        status_text = self.font_small.render(f"状态: {self.connection_status}", True, Colors.TEXT_SECONDARY)
        self.screen.blit(status_text, (info_x, info_y))
        info_y += line_height

        # 任务状态
        task_status = "无" if not self.connection_task else ("运行中" if not self.connection_task.done() else "已完成")
        task_text = self.font_small.render(f"连接任务: {task_status}", True, Colors.TEXT_SECONDARY)
        self.screen.blit(task_text, (info_x, info_y))
        info_y += line_height

        # 玩家信息
        if self.my_color:
            color_text = self.font_small.render(f"你的颜色: {self.my_color['name']}", True, self.my_color['head'])
            self.screen.blit(color_text, (info_x, info_y))
            info_y += line_height

        # 在线玩家数
        if self.game_state and "snakes" in self.game_state:
            alive_count = sum(1 for snake in self.game_state["snakes"].values() if snake["alive"])
            total_count = len(self.game_state["snakes"])
            players_text = self.font_small.render(f"在线玩家: {alive_count}/{total_count}", True, Colors.TEXT_SECONDARY)
            self.screen.blit(players_text, (info_x, info_y))
            info_y += line_height

        # 窗口和网格信息
        size_text = self.font_small.render(f"窗口: {self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}", True, Colors.TEXT_SECONDARY)
        self.screen.blit(size_text, (info_x, info_y))
        info_y += line_height

        grid_text = self.font_small.render(f"网格大小: {self.GRID_SIZE}px", True, Colors.TEXT_SECONDARY)
        self.screen.blit(grid_text, (info_x, info_y))
        info_y += line_height * 2

        # 分数排行榜
        if self.game_state and "snakes" in self.game_state:
            title_text = self.font_medium.render("分数排行榜", True, Colors.TEXT_PRIMARY)
            self.screen.blit(title_text, (info_x, info_y))
            info_y += 35

            # 按分数排序
            sorted_snakes = sorted(
                [(pid, data) for pid, data in self.game_state["snakes"].items()],
                key=lambda x: x[1]["score"],
                reverse=True
            )

            for i, (player_id, snake_data) in enumerate(sorted_snakes[:5]):
                color_info = self.colors[snake_data["color_index"]] if snake_data["color_index"] < len(self.colors) else {"name": "未知", "head": Colors.TEXT_SECONDARY}
                status = "存活" if snake_data["alive"] else "死亡"
                is_me = " (你)" if player_id == self.player_id else ""

                score_text = self.font_small.render(
                    f"{i + 1}. {color_info['name']}: {snake_data['score']} ({status}){is_me}",
                    True,
                    color_info["head"] if snake_data["alive"] else Colors.TEXT_SECONDARY
                )
                self.screen.blit(score_text, (info_x, info_y))
                info_y += line_height

        # 右下角控制说明
        controls = [
            "控制说明:",
            "WASD 或 方向键 - 移动",
            "ESC - 退出游戏",
            "拖拽窗口边缘 - 调整大小"
        ]

        control_x = self.WINDOW_WIDTH - 280
        control_y = self.WINDOW_HEIGHT - len(controls) * 20 - 20

        for control in controls:
            control_text = self.font_small.render(control, True, Colors.TEXT_SECONDARY)
            self.screen.blit(control_text, (control_x, control_y))
            control_y += 20

        # 绘制调试信息
        self.draw_debug_info()

    def draw_connection_screen(self):
        """绘制连接界面"""
        # 标题
        title_text = self.font_large.render("贪吃蛇Online", True, Colors.TEXT_PRIMARY)
        title_rect = title_text.get_rect(center=(self.WINDOW_WIDTH // 2, self.WINDOW_HEIGHT // 2 - 120))
        self.screen.blit(title_text, title_rect)

        # 连接状态
        status_text = self.font_medium.render(self.connection_status, True, Colors.TEXT_SECONDARY)
        status_rect = status_text.get_rect(center=(self.WINDOW_WIDTH // 2, self.WINDOW_HEIGHT // 2 - 70))
        self.screen.blit(status_text, status_rect)

        # 任务状态
        if self.connection_task:
            task_status = "连接任务运行中..." if not self.connection_task.done() else "连接任务已完成"
            task_text = self.font_small.render(task_status, True, Colors.TEXT_SECONDARY)
            task_rect = task_text.get_rect(center=(self.WINDOW_WIDTH // 2, self.WINDOW_HEIGHT // 2 - 40))
            self.screen.blit(task_text, task_rect)

        # 说明
        if not self.connected and not self.pending_connection:
            instruction_text = self.font_small.render("按 SPACE 键连接服务器", True, Colors.TEXT_SECONDARY)
            instruction_rect = instruction_text.get_rect(center=(self.WINDOW_WIDTH // 2, self.WINDOW_HEIGHT // 2 - 10))
            self.screen.blit(instruction_text, instruction_rect)
        elif self.pending_connection:
            connecting_text = self.font_small.render("正在连接中，请稍候...", True, Colors.TEXT_SECONDARY)
            connecting_rect = connecting_text.get_rect(center=(self.WINDOW_WIDTH // 2, self.WINDOW_HEIGHT // 2 - 10))
            self.screen.blit(connecting_text, connecting_rect)

        # 窗口大小提示
        size_text = self.font_small.render(f"窗口大小: {self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT} (可拖拽调整)", True, Colors.TEXT_SECONDARY)
        size_rect = size_text.get_rect(center=(self.WINDOW_WIDTH // 2, self.WINDOW_HEIGHT // 2 + 30))
        self.screen.blit(size_text, size_rect)

        # 服务器信息
        server_text = self.font_small.render("服务器地址: ws://localhost:8765", True, Colors.TEXT_SECONDARY)
        server_rect = server_text.get_rect(center=(self.WINDOW_WIDTH // 2, self.WINDOW_HEIGHT // 2 + 60))
        self.screen.blit(server_text, server_rect)

        # 绘制调试信息
        self.draw_debug_info()

    async def handle_events(self):
        """处理pygame事件"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            elif event.type == pygame.VIDEORESIZE:
                # 处理窗口大小调整
                new_width = max(self.MIN_WIDTH, event.w)
                new_height = max(self.MIN_HEIGHT, event.h)

                self.WINDOW_WIDTH = new_width
                self.WINDOW_HEIGHT = new_height
                self.screen = pygame.display.set_mode((self.WINDOW_WIDTH, self.WINDOW_HEIGHT), pygame.RESIZABLE)

                # 重新计算游戏区域布局
                self.update_game_layout()

                self.add_debug_info(f"* 窗口大小调整为: {self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")

            elif event.type == pygame.KEYDOWN:
                if not self.connected and not self.pending_connection:
                    if event.key == pygame.K_SPACE:
                        # 立即开始连接任务
                        self.add_debug_info("* 检测到空格键，创建连接任务")
                        self.connection_task = asyncio.create_task(self.connect_to_server())
                        self.add_debug_info(f"* 连接任务已创建: {self.connection_task}")
                else:
                    # 游戏控制
                    direction_map = {
                        pygame.K_UP: "UP",
                        pygame.K_w: "UP",
                        pygame.K_DOWN: "DOWN",
                        pygame.K_s: "DOWN",
                        pygame.K_LEFT: "LEFT",
                        pygame.K_a: "LEFT",
                        pygame.K_RIGHT: "RIGHT",
                        pygame.K_d: "RIGHT"
                    }

                    if event.key in direction_map:
                        await self.send_direction(direction_map[event.key])
                    elif event.key == pygame.K_ESCAPE:
                        return False

        return True

    async def run(self):
        """主游戏循环"""
        running = True

        print("* 贪吃蛇Online游戏客户端已启动")
        print("* 提示: 可以拖拽窗口边缘来调整大小")
        print("* 调试模式已启用，可以看到详细的连接信息")

        while running:
            # 处理事件
            running = await self.handle_events()

            if not running:
                break

            # 处理连接任务
            if self.connection_task:
                if self.connection_task.done():
                    try:
                        result = await self.connection_task
                        self.add_debug_info(f"* 连接任务完成，结果: {result}")
                    except Exception as e:
                        self.add_debug_info(f"* 连接任务异常: {e}")
                    finally:
                        self.connection_task = None
                else:
                    # 给异步任务执行的机会
                    await asyncio.sleep(0)

            # 处理网络消息
            self.process_messages()

            # 绘制
            self.draw_gradient_background()

            if self.connected and self.game_state:
                self.draw_game_grid()
                self.draw_snakes()
                self.draw_foods()
                self.draw_ui()
            else:
                self.draw_connection_screen()

            pygame.display.flip()
            self.clock.tick(60)  # 60 FPS

            # 给事件循环机会执行其他任务
            await asyncio.sleep(0.001)  # 1毫秒的休眠，让事件循环调度其他任务

        # 清理
        if self.connection_task and not self.connection_task.done():
            self.add_debug_info("* 取消连接任务")
            self.connection_task.cancel()
        if self.websocket:
            self.add_debug_info("* 关闭WebSocket连接")
            await self.websocket.close()
        pygame.quit()


async def main():
    print("* 贪吃蛇Online游戏客户端启动中...")
    client = SnakeClient()
    await client.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n* 游戏已退出")
