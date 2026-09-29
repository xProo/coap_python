import asyncio
import aiocoap


async def main():
    ctx = await aiocoap.Context.create_client_context()
    req = aiocoap.Message(code=aiocoap.GET, uri="coap://127.0.0.1/temp")
    req.opt.observe = 0
    requester = ctx.request(req)
    try:
        async with asyncio.timeout(10):
            async for response in requester.observation:
                print(response.payload.decode(), flush=True)
    except TimeoutError:
        pass
    if not requester.observation.cancelled:
        requester.observation.cancel()
    await ctx.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
