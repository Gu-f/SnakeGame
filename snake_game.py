import pygame
import random
import json
import os
import platform
from enum import Enum
from typing import List, Tuple
import math

pygame.init()


class GameState(Enum):
    MENU = 1
    PLAYING = 2
    PAUSED = 3
    GAME_OVER = 4


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
    SNAKE_HEAD = (76, 175, 80)
    SNAKE_BODY = (139, 195, 74)
    FOOD = (244, 67, 54)
    FOOD_GLOW = (255, 138, 128)
    TEXT_PRIMARY = (255, 255, 255)
    TEXT_SECONDARY = (189, 189, 189)
    BUTTON_BG = (63, 81, 181)
    BUTTON_HOVER = (92, 107, 192)
    GRID_LINE = (40, 40, 70)
    SHADOW = (0, 0, 0, 50)


def get_chinese_font(size):
    """获取支持中文的字体"""
    system = platform.system()

    # 兼容多系统
    chinese_fonts = []

    if system == "Windows":
        chinese_fonts = [
            "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",  # 黑体
            "C:/Windows/Fonts/simsun.ttc",  # 宋体
            "C:/Windows/Fonts/arial.ttf",  # Arial (fallback)
        ]
    elif system == "Darwin":  # macOS
        chinese_fonts = [
            "/System/Library/Fonts/PingFang.ttc",  # 苹方
            "/System/Library/Fonts/STHeiti Light.ttc",  # 黑体
            "/System/Library/Fonts/Hiragino Sans GB.ttc",  # 冬青黑体
            "/System/Library/Fonts/Arial.ttf",  # Arial (fallback)
        ]
    else:  # Linux
        chinese_fonts = [
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # 文泉驿微米黑
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",  # 文泉驿正黑
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # DejaVu Sans
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]

    for font_path in chinese_fonts:
        try:
            if os.path.exists(font_path):
                return pygame.font.Font(font_path, size)
        except Exception as e:
            continue


class Snake:
    def __init__(self, start_pos: Tuple[int, int]):
        self.body = [start_pos, (start_pos[0] - 1, start_pos[1]), (start_pos[0] - 2, start_pos[1])]
        self.direction = Direction.RIGHT
        self.grow_pending = False

    def move(self):
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

    def check_collision(self, grid_width: int, grid_height: int) -> bool:
        head = self.body[0]
        # 检查墙壁碰撞
        if (head[0] < 0 or head[0] >= grid_width or
                head[1] < 0 or head[1] >= grid_height):
            return True
        # 检查自身碰撞
        return head in self.body[1:]


class Food:
    def __init__(self, grid_width: int, grid_height: int, snake_body: List[Tuple[int, int]]):
        self.position = self.generate_position(grid_width, grid_height, snake_body)
        self.pulse_offset = 0

    def generate_position(self, grid_width: int, grid_height: int, snake_body: List[Tuple[int, int]]) -> Tuple[int, int]:
        while True:
            pos = (random.randint(0, grid_width - 1), random.randint(0, grid_height - 1))
            if pos not in snake_body:
                return pos

    def update_pulse(self):
        self.pulse_offset += 0.2


class SnakeGame:
    def __init__(self):
        self.WINDOW_WIDTH = 1000
        self.WINDOW_HEIGHT = 700
        self.GRID_SIZE = 25
        self.GRID_WIDTH = 32
        self.GRID_HEIGHT = 20

        self.screen = pygame.display.set_mode((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
        pygame.display.set_caption("贪吃蛇 - Snake Game")

        self.clock = pygame.time.Clock()

        # 使用支持中文的字体
        self.font_large = get_chinese_font(48)
        self.font_medium = get_chinese_font(32)
        self.font_small = get_chinese_font(24)

        self.game_state = GameState.MENU
        self.snake = None
        self.food = None
        self.score = 0
        self.high_score = self.load_high_score()
        self.game_speed = 8

        # 动画相关
        self.transition_alpha = 0
        self.button_hover_states = {}

        # 游戏区域偏移（居中显示）
        self.game_offset_x = (self.WINDOW_WIDTH - self.GRID_WIDTH * self.GRID_SIZE) // 2
        self.game_offset_y = (self.WINDOW_HEIGHT - self.GRID_HEIGHT * self.GRID_SIZE) // 2 + 30

    def load_high_score(self) -> int:
        try:
            if os.path.exists('high_score.json'):
                with open('high_score.json', 'r') as f:
                    return json.load(f).get('high_score', 0)
        except:
            pass
        return 0

    def save_high_score(self):
        try:
            with open('high_score.json', 'w') as f:
                json.dump({'high_score': self.high_score}, f)
        except:
            pass

    def start_new_game(self):
        start_pos = (self.GRID_WIDTH // 2, self.GRID_HEIGHT // 2)
        self.snake = Snake(start_pos)
        self.food = Food(self.GRID_WIDTH, self.GRID_HEIGHT, self.snake.body)
        self.score = 0
        self.game_speed = 8
        self.game_state = GameState.PLAYING

    def draw_gradient_background(self):
        for y in range(self.WINDOW_HEIGHT):
            ratio = y / self.WINDOW_HEIGHT
            r = int(Colors.GRADIENT_START[0] * (1 - ratio) + Colors.GRADIENT_END[0] * ratio)
            g = int(Colors.GRADIENT_START[1] * (1 - ratio) + Colors.GRADIENT_END[1] * ratio)
            b = int(Colors.GRADIENT_START[2] * (1 - ratio) + Colors.GRADIENT_END[2] * ratio)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (self.WINDOW_WIDTH, y))

    def draw_rounded_rect(self, surface, color, rect, radius):
        pygame.draw.rect(surface, color, rect, border_radius=radius)

    def draw_shadow_rect(self, surface, rect, radius, offset=(3, 3)):
        shadow_surface = pygame.Surface((rect.width + offset[0], rect.height + offset[1]), pygame.SRCALPHA)
        shadow_rect = pygame.Rect(offset[0], offset[1], rect.width, rect.height)
        self.draw_rounded_rect(shadow_surface, Colors.SHADOW, shadow_rect, radius)
        surface.blit(shadow_surface, (rect.x - offset[0] // 2, rect.y - offset[1] // 2))

    def draw_button(self, text, x, y, width, height, button_id):
        mouse_pos = pygame.mouse.get_pos()
        button_rect = pygame.Rect(x, y, width, height)
        is_hovered = button_rect.collidepoint(mouse_pos)

        # 悬停动画
        if button_id not in self.button_hover_states:
            self.button_hover_states[button_id] = 0

        target_hover = 1.0 if is_hovered else 0.0
        self.button_hover_states[button_id] += (target_hover - self.button_hover_states[button_id]) * 0.1

        # 绘制阴影
        self.draw_shadow_rect(self.screen, button_rect, 10)

        # 按钮颜色插值
        hover_ratio = self.button_hover_states[button_id]
        button_color = (
            int(Colors.BUTTON_BG[0] * (1 - hover_ratio) + Colors.BUTTON_HOVER[0] * hover_ratio),
            int(Colors.BUTTON_BG[1] * (1 - hover_ratio) + Colors.BUTTON_HOVER[1] * hover_ratio),
            int(Colors.BUTTON_BG[2] * (1 - hover_ratio) + Colors.BUTTON_HOVER[2] * hover_ratio)
        )

        self.draw_rounded_rect(self.screen, button_color, button_rect, 10)

        # 绘制文字
        text_surface = self.font_medium.render(text, True, Colors.TEXT_PRIMARY)
        text_rect = text_surface.get_rect(center=button_rect.center)
        self.screen.blit(text_surface, text_rect)

        return is_hovered and pygame.mouse.get_pressed()[0]

    def draw_game_grid(self):
        # 绘制游戏区域背景
        game_rect = pygame.Rect(
            self.game_offset_x - 10,
            self.game_offset_y - 10,
            self.GRID_WIDTH * self.GRID_SIZE + 20,
            self.GRID_HEIGHT * self.GRID_SIZE + 20
        )
        self.draw_shadow_rect(self.screen, game_rect, 15)
        self.draw_rounded_rect(self.screen, (25, 25, 45), game_rect, 15)

        # 绘制网格线
        for x in range(self.GRID_WIDTH + 1):
            start_pos = (self.game_offset_x + x * self.GRID_SIZE, self.game_offset_y)
            end_pos = (self.game_offset_x + x * self.GRID_SIZE, self.game_offset_y + self.GRID_HEIGHT * self.GRID_SIZE)
            pygame.draw.line(self.screen, Colors.GRID_LINE, start_pos, end_pos, 1)

        for y in range(self.GRID_HEIGHT + 1):
            start_pos = (self.game_offset_x, self.game_offset_y + y * self.GRID_SIZE)
            end_pos = (self.game_offset_x + self.GRID_WIDTH * self.GRID_SIZE, self.game_offset_y + y * self.GRID_SIZE)
            pygame.draw.line(self.screen, Colors.GRID_LINE, start_pos, end_pos, 1)

    def draw_snake(self):
        for i, segment in enumerate(self.snake.body):
            x = self.game_offset_x + segment[0] * self.GRID_SIZE
            y = self.game_offset_y + segment[1] * self.GRID_SIZE

            # 蛇头特殊处理
            if i == 0:
                # 绘制阴影
                shadow_rect = pygame.Rect(x + 2, y + 2, self.GRID_SIZE - 4, self.GRID_SIZE - 4)
                self.draw_rounded_rect(self.screen, Colors.SHADOW, shadow_rect, 8)

                # 绘制蛇头
                head_rect = pygame.Rect(x + 2, y + 2, self.GRID_SIZE - 4, self.GRID_SIZE - 4)
                self.draw_rounded_rect(self.screen, Colors.SNAKE_HEAD, head_rect, 8)

                # 绘制眼睛
                eye_size = 3
                if self.snake.direction == Direction.UP:
                    eye1_pos = (x + 8, y + 6)
                    eye2_pos = (x + 16, y + 6)
                elif self.snake.direction == Direction.DOWN:
                    eye1_pos = (x + 8, y + 16)
                    eye2_pos = (x + 16, y + 16)
                elif self.snake.direction == Direction.LEFT:
                    eye1_pos = (x + 6, y + 8)
                    eye2_pos = (x + 6, y + 16)
                else:  # RIGHT
                    eye1_pos = (x + 18, y + 8)
                    eye2_pos = (x + 18, y + 16)

                pygame.draw.circle(self.screen, Colors.TEXT_PRIMARY, eye1_pos, eye_size)
                pygame.draw.circle(self.screen, Colors.TEXT_PRIMARY, eye2_pos, eye_size)
            else:
                # 蛇身
                body_rect = pygame.Rect(x + 3, y + 3, self.GRID_SIZE - 6, self.GRID_SIZE - 6)
                self.draw_rounded_rect(self.screen, Colors.SNAKE_BODY, body_rect, 6)

    def draw_food(self):
        x = self.game_offset_x + self.food.position[0] * self.GRID_SIZE
        y = self.game_offset_y + self.food.position[1] * self.GRID_SIZE

        # 脉冲效果
        pulse_size = int(3 * math.sin(self.food.pulse_offset))

        # 绘制光晕
        glow_rect = pygame.Rect(x - pulse_size, y - pulse_size,
                                self.GRID_SIZE + pulse_size * 2,
                                self.GRID_SIZE + pulse_size * 2)
        glow_surface = pygame.Surface((glow_rect.width, glow_rect.height), pygame.SRCALPHA)
        pygame.draw.circle(glow_surface, (*Colors.FOOD_GLOW, 50),
                           (glow_rect.width // 2, glow_rect.height // 2),
                           glow_rect.width // 2)
        self.screen.blit(glow_surface, glow_rect)

        # 绘制食物
        food_rect = pygame.Rect(x + 3, y + 3, self.GRID_SIZE - 6, self.GRID_SIZE - 6)
        pygame.draw.circle(self.screen, Colors.FOOD, food_rect.center, (self.GRID_SIZE - 6) // 2)

        self.food.update_pulse()

    def draw_ui(self):
        # 得分显示
        score_text = self.font_medium.render(f"得分: {self.score}", True, Colors.TEXT_PRIMARY)
        self.screen.blit(score_text, (20, 20))

        high_score_text = self.font_small.render(f"最高分: {self.high_score}", True, Colors.TEXT_SECONDARY)
        self.screen.blit(high_score_text, (20, 55))

        # 控制提示
        if self.game_state == GameState.PLAYING:
            controls_text = self.font_small.render("方向键/WASD移动 | 空格暂停 | ESC退出", True, Colors.TEXT_SECONDARY)
            text_rect = controls_text.get_rect()
            text_rect.centerx = self.WINDOW_WIDTH // 2
            text_rect.bottom = self.WINDOW_HEIGHT - 20
            self.screen.blit(controls_text, text_rect)

    def draw_menu(self):
        # 标题
        title_text = self.font_large.render("贪吃蛇", True, Colors.TEXT_PRIMARY)
        title_rect = title_text.get_rect(center=(self.WINDOW_WIDTH // 2, 150))
        self.screen.blit(title_text, title_rect)

        # 最高分显示
        if self.high_score > 0:
            high_score_text = self.font_medium.render(f"最高分: {self.high_score}", True, Colors.TEXT_SECONDARY)
            high_score_rect = high_score_text.get_rect(center=(self.WINDOW_WIDTH // 2, 200))
            self.screen.blit(high_score_text, high_score_rect)

        # 开始按钮
        if self.draw_button("开始游戏", self.WINDOW_WIDTH // 2 - 100, 300, 200, 50, "start"):
            self.start_new_game()

        # 退出按钮
        if self.draw_button("退出游戏", self.WINDOW_WIDTH // 2 - 100, 370, 200, 50, "quit"):
            return False

        return True

    def draw_pause_menu(self):
        # 半透明覆盖层
        overlay = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        # 暂停文字
        pause_text = self.font_large.render("游戏暂停", True, Colors.TEXT_PRIMARY)
        pause_rect = pause_text.get_rect(center=(self.WINDOW_WIDTH // 2, 250))
        self.screen.blit(pause_text, pause_rect)

        # 继续按钮
        if self.draw_button("继续游戏", self.WINDOW_WIDTH // 2 - 100, 320, 200, 50, "resume"):
            self.game_state = GameState.PLAYING

        # 重新开始按钮
        if self.draw_button("重新开始", self.WINDOW_WIDTH // 2 - 100, 390, 200, 50, "restart"):
            self.start_new_game()

        # 返回菜单按钮
        if self.draw_button("返回菜单", self.WINDOW_WIDTH // 2 - 100, 460, 200, 50, "menu"):
            self.game_state = GameState.MENU

    def draw_game_over(self):
        # 半透明覆盖层
        overlay = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        # 游戏结束文字
        game_over_text = self.font_large.render("游戏结束", True, Colors.TEXT_PRIMARY)
        game_over_rect = game_over_text.get_rect(center=(self.WINDOW_WIDTH // 2, 200))
        self.screen.blit(game_over_text, game_over_rect)

        # 最终得分
        final_score_text = self.font_medium.render(f"最终得分: {self.score}", True, Colors.TEXT_SECONDARY)
        final_score_rect = final_score_text.get_rect(center=(self.WINDOW_WIDTH // 2, 250))
        self.screen.blit(final_score_text, final_score_rect)

        # 新纪录提示
        if self.score == self.high_score and self.score > 0:
            new_record_text = self.font_medium.render("新纪录！", True, Colors.FOOD)
            new_record_rect = new_record_text.get_rect(center=(self.WINDOW_WIDTH // 2, 290))
            self.screen.blit(new_record_text, new_record_rect)

        # 重新开始按钮
        if self.draw_button("重新开始", self.WINDOW_WIDTH // 2 - 100, 350, 200, 50, "restart_go"):
            self.start_new_game()

        # 返回菜单按钮
        if self.draw_button("返回菜单", self.WINDOW_WIDTH // 2 - 100, 420, 200, 50, "menu_go"):
            self.game_state = GameState.MENU

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                if self.game_state == GameState.PLAYING:
                    # 方向控制
                    if event.key in [pygame.K_UP, pygame.K_w]:
                        self.snake.change_direction(Direction.UP)
                    elif event.key in [pygame.K_DOWN, pygame.K_s]:
                        self.snake.change_direction(Direction.DOWN)
                    elif event.key in [pygame.K_LEFT, pygame.K_a]:
                        self.snake.change_direction(Direction.LEFT)
                    elif event.key in [pygame.K_RIGHT, pygame.K_d]:
                        self.snake.change_direction(Direction.RIGHT)
                    elif event.key == pygame.K_SPACE:
                        self.game_state = GameState.PAUSED
                    elif event.key == pygame.K_ESCAPE:
                        self.game_state = GameState.MENU

                elif self.game_state == GameState.PAUSED:
                    if event.key == pygame.K_SPACE:
                        self.game_state = GameState.PLAYING
                    elif event.key == pygame.K_ESCAPE:
                        self.game_state = GameState.MENU

                elif self.game_state in [GameState.MENU, GameState.GAME_OVER]:
                    if event.key == pygame.K_RETURN:
                        self.start_new_game()
                    elif event.key == pygame.K_ESCAPE and self.game_state == GameState.MENU:
                        return False

        return True

    def update_game(self):
        if self.game_state != GameState.PLAYING:
            return

        # 移动蛇
        self.snake.move()

        # 检查食物碰撞
        if self.snake.body[0] == self.food.position:
            self.snake.grow()
            self.score += 10
            if self.score > self.high_score:
                self.high_score = self.score
                self.save_high_score()

            # 生成新食物
            self.food = Food(self.GRID_WIDTH, self.GRID_HEIGHT, self.snake.body)

            # 增加游戏速度
            if self.game_speed < 15:
                self.game_speed += 0.2

        # 检查碰撞
        if self.snake.check_collision(self.GRID_WIDTH, self.GRID_HEIGHT):
            self.game_state = GameState.GAME_OVER

    def run(self):
        running = True

        while running:
            running = self.handle_events()

            if not running:
                break

            self.update_game()

            # 绘制
            self.draw_gradient_background()

            if self.game_state == GameState.MENU:
                running = self.draw_menu()

            elif self.game_state in [GameState.PLAYING, GameState.PAUSED]:
                self.draw_game_grid()
                if self.snake:
                    self.draw_snake()
                if self.food:
                    self.draw_food()
                self.draw_ui()

                if self.game_state == GameState.PAUSED:
                    self.draw_pause_menu()

            elif self.game_state == GameState.GAME_OVER:
                self.draw_game_grid()
                if self.snake:
                    self.draw_snake()
                if self.food:
                    self.draw_food()
                self.draw_ui()
                self.draw_game_over()

            pygame.display.flip()
            self.clock.tick(self.game_speed if self.game_state == GameState.PLAYING else 60)

        pygame.quit()


if __name__ == "__main__":
    print("启动贪吃蛇游戏...")

    game = SnakeGame()
    game.run()
