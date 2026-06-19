"""
Application runner for Google Colab.

Uses uvicorn with asyncio server directly to avoid the nest_asyncio
conflict with uvicorn's loop_factory parameter.
"""

import sys
import asyncio
import traceback


def main():
    """Start the FastAPI application using uvicorn."""
    try:
        import uvicorn
        from app.main import app

        print("Application imported successfully")
        print(f"Routes registered: {len(app.routes)}")

        # Create uvicorn config and server manually
        # This avoids the nest_asyncio + loop_factory conflict
        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            loop="asyncio",
        )
        server = uvicorn.Server(config)

        # Run using asyncio directly (compatible with nest_asyncio)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(server.serve())
        except KeyboardInterrupt:
            print("\nServer stopped by user")
        finally:
            loop.close()

    except Exception as e:
        print(f"FATAL ERROR: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
