import asyncio
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

async def test_db():
    try:
        from app.database import writer_session, reader_sessions
        print(f"writer_session type: {type(writer_session)}")
        print(f"reader_sessions type: {type(reader_sessions)}")
        
        session = writer_session()
        print(f"session object type: {type(session)}")
        print(f"session has __aenter__: {hasattr(session, '__aenter__')}")
        
        async with session as s:
            print("Successfully entered session context")
            
    except Exception as e:
        print(f"Test failed with error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_db())
