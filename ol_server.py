import asyncio
from online.snake_game_ol_server import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n* 服务器已关闭")
