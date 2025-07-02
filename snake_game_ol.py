import asyncio
from online.snake_game_ol_client import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n* 游戏已退出")
