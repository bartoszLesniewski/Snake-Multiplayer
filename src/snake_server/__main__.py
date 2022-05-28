import asyncio

from .app import App


def _cancel_all_tasks(loop: asyncio.AbstractEventLoop) -> None:
    to_cancel = asyncio.all_tasks(loop)
    if not to_cancel:
        return

    for task in to_cancel:
        task.cancel()

    loop.run_until_complete(asyncio.gather(*to_cancel, return_exceptions=True))

    for task in to_cancel:
        if task.cancelled():
            continue
        if (exception := task.exception()) is not None:
            loop.call_exception_handler(
                {
                    "message": "unhandled exception during shutdown",
                    "exception": exception,
                    "task": task,
                }
            )


async def run_app() -> int:
    app = App()
    try:
        return await app.run()
    finally:
        await app.close()


def main() -> int:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run_app())
    except KeyboardInterrupt:
        print("Ctrl+C received, exiting...")
        return 0
    finally:
        try:
            _cancel_all_tasks(loop)
            print("Sleeping for 2 seconds to allow proper loop cleanup...")
            loop.run_until_complete(asyncio.sleep(2))
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
        finally:
            asyncio.set_event_loop(None)
            loop.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        pass
