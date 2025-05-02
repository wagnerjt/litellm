uvicorn litellm.proxy.proxy_server:app --reload --host localhost --port 4000

# prisma
# prisma generate --schema=./litellm/proxy/schema.prisma
# prisma db push --schema=./litellm/proxy/schema.prisma

# todo: mount to existing asgi server
# https://pypi.org/project/mcp/