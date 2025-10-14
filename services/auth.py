from services.api.auth_api import TSUAuth

auth = TSUAuth()

async def shutdown():
    await auth.close_session()
