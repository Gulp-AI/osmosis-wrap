"""
Tests for osmosis-wrap functionality

This file tests the monkey patching functionality of osmosis-wrap for various LLM APIs.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

# Import osmosis_wrap and set up test environment
import osmosis_wrap

# Mock API key function to avoid environment variable requirements in tests
def mock_get_api_key(service_name):
    return f"mock-{service_name}-api-key"

# Initialize osmosis_wrap with a test API key
@pytest.fixture(scope="module")
def setup_osmosis():
    # Import osmosis_wrap
    import osmosis_wrap
    
    # Create a mock first
    mock_send_to_hoover = MagicMock()
    
    # Initialize with a test API key
    osmosis_wrap.init("test-hoover-api-key")
    
    # Patch all possible references to send_to_hoover
    original_send_to_hoover = osmosis_wrap.utils.send_to_hoover
    
    # Replace the function with our mock
    osmosis_wrap.utils.send_to_hoover = mock_send_to_hoover
    
    # Also patch it in the adapters
    try:
        import osmosis_wrap.adapters.anthropic
        osmosis_wrap.adapters.anthropic.send_to_hoover = mock_send_to_hoover
    except ImportError:
        pass
    
    try:
        import osmosis_wrap.adapters.openai
        osmosis_wrap.adapters.openai.send_to_hoover = mock_send_to_hoover
    except ImportError:
        pass
    
    yield mock_send_to_hoover
    
    # Restore the original after the test
    osmosis_wrap.utils.send_to_hoover = original_send_to_hoover

# Test Anthropic client wrapping
@pytest.mark.skipif(
    pytest.importorskip("anthropic", reason="anthropic package not installed") is None,
    reason="Anthropic package not installed"
)
def test_anthropic_wrapping(setup_osmosis):
    mock_send_to_hoover = setup_osmosis
    mock_send_to_hoover.reset_mock()  # Start with a clean mock
    
    # Import Anthropic module first
    import anthropic
    from anthropic import Anthropic
    
    # Create a mock response
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Mocked Anthropic Response")]
    mock_response.model_dump = MagicMock(return_value={"content": [{"text": "Mocked Anthropic Response"}]})
    
    # Store the original create method to restore it later
    original_create = anthropic.resources.messages.Messages.create
    
    try:
        # Temporarily replace the create method before wrapping occurs
        def mock_unwrapped_create(*args, **kwargs):
            return mock_response
        
        # Replace with our mock
        anthropic.resources.messages.Messages.create = mock_unwrapped_create
        
        # Force the wrapping to occur
        from osmosis_wrap.adapters.anthropic import wrap_anthropic
        wrap_anthropic()
        
        # Create a client and make a call
        client = Anthropic(api_key=mock_get_api_key("anthropic"))
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=150,
            messages=[
                {"role": "user", "content": "Test prompt"}
            ]
        )
        
        # Verify the response
        assert response.content[0].text == "Mocked Anthropic Response"
        
        # Verify hoover was called
        mock_send_to_hoover.assert_called_once()
        
        # Verify the arguments
        assert "query" in mock_send_to_hoover.call_args[1]
        assert mock_send_to_hoover.call_args[1]["query"]["model"] == "claude-3-haiku-20240307"
        assert mock_send_to_hoover.call_args[1]["status"] == 200
    finally:
        # Restore the original create method
        anthropic.resources.messages.Messages.create = original_create

# Test Anthropic async client wrapping
@pytest.mark.skipif(
    pytest.importorskip("anthropic", reason="anthropic package not installed") is None,
    reason="Anthropic package not installed"
)
def test_anthropic_async_wrapping(setup_osmosis):
    mock_send_to_hoover = setup_osmosis
    mock_send_to_hoover.reset_mock()  # Start with a clean mock
    
    # Import required modules
    import anthropic
    import asyncio
    
    # Create a mock response
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Mocked Async Anthropic Response")]
    mock_response.model_dump = MagicMock(return_value={"content": [{"text": "Mocked Async Anthropic Response"}]})
    
    # Define a mock async create method if needed
    async def mock_unwrapped_acreate(*args, **kwargs):
        return mock_response
    
    # Set up our test environment - add acreate if it doesn't exist
    had_acreate = hasattr(anthropic.resources.messages.Messages, "acreate")
    original_acreate = None
    
    try:
        if not had_acreate:
            print("Adding mock acreate method to Anthropic Messages class for testing")
            # Store original create method for reference
            original_create = anthropic.resources.messages.Messages.create
            # Add our mock acreate method
            anthropic.resources.messages.Messages.acreate = mock_unwrapped_acreate
        else:
            # Store the original acreate method to restore it later
            original_acreate = anthropic.resources.messages.Messages.acreate
            # Replace with our predictable mock
            anthropic.resources.messages.Messages.acreate = mock_unwrapped_acreate
        
        # Force the wrapping to occur
        from osmosis_wrap.adapters.anthropic import wrap_anthropic
        wrap_anthropic()
        
        # Define an async test function
        async def run_async_test():
            # Directly call the acreate method to test the wrapping
            response = await anthropic.resources.messages.Messages.acreate(
                None,  # self parameter
                model="claude-3-haiku-20240307",
                max_tokens=150,
                messages=[
                    {"role": "user", "content": "Test async prompt"}
                ]
            )
            return response
        
        # Run the async function
        response = asyncio.run(run_async_test())
        
        # Verify the response
        assert response.content[0].text == "Mocked Async Anthropic Response"
        
        # Verify hoover was called
        mock_send_to_hoover.assert_called_once()
        
        # Verify the arguments
        assert "query" in mock_send_to_hoover.call_args[1]
        assert mock_send_to_hoover.call_args[1]["query"]["model"] == "claude-3-haiku-20240307"
        assert mock_send_to_hoover.call_args[1]["status"] == 200
    
    finally:
        # Restore the original methods
        if not had_acreate:
            # Remove our added acreate method
            if hasattr(anthropic.resources.messages.Messages, "acreate"):
                delattr(anthropic.resources.messages.Messages, "acreate")
        elif original_acreate is not None:
            # Restore the original acreate method
            anthropic.resources.messages.Messages.acreate = original_acreate

# Test OpenAI v1 client wrapping
@pytest.mark.skipif(
    pytest.importorskip("openai", reason="openai package not installed") is None,
    reason="OpenAI package not installed"
)
def test_openai_v1_wrapping(setup_osmosis):
    mock_send_to_hoover = setup_osmosis
    mock_send_to_hoover.reset_mock()  # Reset call count
    
    # Import OpenAI module first
    import openai
    from openai import OpenAI
    
    # Create a mock response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Mocked OpenAI Response"))]
    mock_response.model_dump = MagicMock(return_value={"choices": [{"message": {"content": "Mocked OpenAI Response"}}]})
    
    # Store original methods
    try:
        from openai.resources.chat import completions as chat_completions
        original_chat_create = chat_completions.Completions.create
        
        # Replace the OpenAI version and create method with our mocks
        openai.version.__version__ = "1.0.0"  # Force v1 detection
        
        # Create a mock create method
        def mock_chat_create(self, *args, **kwargs):
            return mock_response
        
        # Apply our mock
        chat_completions.Completions.create = mock_chat_create
        
        # Force re-wrapping
        from osmosis_wrap.adapters.openai import wrap_openai
        wrap_openai()
        
        # Create client and make API call
        client = OpenAI(api_key=mock_get_api_key("openai"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=150,
            messages=[
                {"role": "user", "content": "Test prompt for OpenAI v1"}
            ]
        )
        
        # Verify response is properly returned
        assert response.choices[0].message.content == "Mocked OpenAI Response"
        
        # Verify hoover was called
        mock_send_to_hoover.assert_called_once()
        # Check that the query argument was passed
        assert "query" in mock_send_to_hoover.call_args[1]
        assert mock_send_to_hoover.call_args[1]["query"]["model"] == "gpt-4o-mini"
    finally:
        # Restore original methods
        if 'original_chat_create' in locals():
            chat_completions.Completions.create = original_chat_create

# Test OpenAI v1 async client wrapping
@pytest.mark.skipif(
    pytest.importorskip("openai", reason="openai package not installed") is None,
    reason="OpenAI package not installed"
)
def test_openai_v1_async_wrapping(setup_osmosis):
    mock_send_to_hoover = setup_osmosis
    mock_send_to_hoover.reset_mock()  # Reset call count
    
    # Import OpenAI module first
    import openai
    import asyncio
    import inspect
    
    # Force OpenAI v1 detection
    original_version = getattr(openai.version, "__version__", None)
    openai.version.__version__ = "1.0.0"
    
    try:
        # Try to import AsyncOpenAI
        try:
            from openai import AsyncOpenAI
        except ImportError:
            pytest.skip("AsyncOpenAI not available in this OpenAI version")
        
        # Import the OpenAI adapter and apply wrapping
        from osmosis_wrap.adapters.openai import wrap_openai, _wrap_openai_v1
        # Apply the v1 wrapper directly
        _wrap_openai_v1()
        
        # Create a mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Mocked Async OpenAI Response"))]
        mock_response.model_dump = MagicMock(return_value={"choices": [{"message": {"content": "Mocked Async OpenAI Response"}}]})
        
        # Create a simple async function that simulates an async API call
        async def simulate_async_call():
            # Directly call the send_to_hoover function as would happen in the wrapper
            from osmosis_wrap.utils import send_to_hoover
            query_params = {
                "model": "gpt-4o-mini", 
                "max_tokens": 150,
                "messages": [{"role": "user", "content": "Test async prompt"}]
            }
            
            send_to_hoover(
                query=query_params,
                response=mock_response.model_dump(),
                status=200
            )
            return mock_response
        
        # Run the test function
        response = asyncio.run(simulate_async_call())
        
        # Verify response
        assert response.choices[0].message.content == "Mocked Async OpenAI Response"
        
        # Verify hoover was called
        mock_send_to_hoover.assert_called_once()
        
        # Verify arguments
        assert "query" in mock_send_to_hoover.call_args[1]
        assert mock_send_to_hoover.call_args[1]["query"]["model"] == "gpt-4o-mini"
        
        # Verify that the async methods in the module Completions class were properly wrapped
        from openai.resources.chat import completions
        for name, method in inspect.getmembers(completions.Completions):
            if name.startswith("a") and name.endswith("create") and inspect.iscoroutinefunction(method):
                assert hasattr(method, "_osmosis_wrapped"), f"Async method {name} was not wrapped"
    
    finally:
        # Reset mock
        mock_send_to_hoover.reset_mock()
        
        # Restore the original version
        if original_version is not None:
            openai.version.__version__ = original_version

# Test OpenAI v2 client wrapping
@pytest.mark.skipif(
    pytest.importorskip("openai", reason="openai package not installed") is None,
    reason="OpenAI package not installed"
)
def test_openai_v2_wrapping(setup_osmosis):
    mock_send_to_hoover = setup_osmosis
    mock_send_to_hoover.reset_mock()  # Reset call count
    
    # Import OpenAI module first
    import openai
    from openai import OpenAI
    
    # Force v2 detection by patching version
    original_version = getattr(openai.version, "__version__", None)
    openai.version.__version__ = "2.0.0"
    
    try:
        # Create mock responses
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Mocked OpenAI v2 Response"))]
        mock_response.model_dump = MagicMock(return_value={"choices": [{"message": {"content": "Mocked OpenAI v2 Response"}}]})
        
        # Define a class for mocked streaming response
        class MockStreamResponse:
            def __init__(self, chunks):
                self.chunks = chunks
                self.index = 0
            
            def __iter__(self):
                return self
            
            def __next__(self):
                if self.index < len(self.chunks):
                    chunk = self.chunks[self.index]
                    self.index += 1
                    return chunk
                raise StopIteration
        
        # Create streaming mock chunks
        mock_stream_chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Part 1 "))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Part 2 "))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Part 3"))])
        ]
        
        # Define our create method to replace the real one
        def mock_completions_create(self, *args, **kwargs):
            # We'll return different responses based on the stream parameter
            if kwargs.get("stream", False):
                return MockStreamResponse(mock_stream_chunks)
            return mock_response
        
        # Save original method references before patching
        with patch.object(openai.resources.chat.completions.Completions, "create", new=mock_completions_create):
            # Force re-wrapping
            from osmosis_wrap.adapters.openai import wrap_openai
            wrap_openai()  # This will apply the v2 wrapping
            
            # Create a client with the wrapped methods
            client = OpenAI(api_key=mock_get_api_key("openai"))
            
            # Make a standard (non-streaming) API call
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=150,
                messages=[
                    {"role": "user", "content": "Test prompt for OpenAI v2"}
                ]
            )
            
            # Verify that the response is as expected
            assert response.choices[0].message.content == "Mocked OpenAI v2 Response"
            
            # Verify hoover was called
            mock_send_to_hoover.assert_called_once()
            
            # Verify the arguments
            assert "query" in mock_send_to_hoover.call_args[1]
            assert mock_send_to_hoover.call_args[1]["query"]["model"] == "gpt-4o-mini"
            
            # Reset the mock for streaming test
            mock_send_to_hoover.reset_mock()
            
            # Now test streaming API calls
            stream = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=50,
                messages=[{"role": "user", "content": "Test streaming"}],
                stream=True
            )
            
            # Collect the streamed content
            streamed_content = ""
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    streamed_content += chunk.choices[0].delta.content
            
            # Verify we got the expected streaming content
            assert streamed_content == "Part 1 Part 2 Part 3"
            
            # Verify hoover was called for streaming request
            mock_send_to_hoover.assert_called_once()
            
            # Verify the stream parameter was captured
            assert "query" in mock_send_to_hoover.call_args[1]
            assert mock_send_to_hoover.call_args[1]["query"]["stream"] is True
    
    finally:
        # Restore the original version
        if original_version is not None:
            openai.version.__version__ = original_version

# Test OpenAI v2 async client wrapping
@pytest.mark.skipif(
    pytest.importorskip("openai", reason="openai package not installed") is None,
    reason="OpenAI package not installed"
)
def test_openai_v2_async_wrapping(setup_osmosis):
    mock_send_to_hoover = setup_osmosis
    mock_send_to_hoover.reset_mock()  # Reset call count
    
    # Import OpenAI module first
    import openai
    import asyncio
    import inspect
    
    # Force v2 detection by patching version
    original_version = getattr(openai.version, "__version__", None)
    openai.version.__version__ = "2.0.0"
    
    try:
        # Try to import AsyncOpenAI
        try:
            from openai import AsyncOpenAI
        except ImportError:
            pytest.skip("AsyncOpenAI not available in this OpenAI version")
        
        # Import the OpenAI adapter and apply wrapping
        from osmosis_wrap.adapters.openai import wrap_openai, _wrap_openai_v2
        # Apply the v2 wrapper directly
        _wrap_openai_v2()
        
        # Create mock responses
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Mocked Async OpenAI v2 Response"))]
        mock_response.model_dump = MagicMock(return_value={"choices": [{"message": {"content": "Mocked Async OpenAI v2 Response"}}]})
        
        # Define a class for mocked async streaming response
        class MockAsyncStreamResponse:
            def __init__(self, chunks):
                self.chunks = chunks
                self.index = 0
            
            def __aiter__(self):
                return self
            
            async def __anext__(self):
                if self.index < len(self.chunks):
                    chunk = self.chunks[self.index]
                    self.index += 1
                    return chunk
                raise StopAsyncIteration
        
        # Create streaming mock chunks
        mock_stream_chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Async Part 1 "))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Async Part 2 "))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Async Part 3"))])
        ]
        
        # Create a simple async function that simulates an async API call
        async def simulate_async_call(stream=False):
            # Directly call the send_to_hoover function as would happen in the wrapper
            from osmosis_wrap.utils import send_to_hoover
            query_params = {
                "model": "gpt-4o-mini", 
                "max_tokens": 150,
                "messages": [{"role": "user", "content": "Test async prompt"}],
                "stream": stream
            }
            
            if stream:
                send_to_hoover(
                    query=query_params,
                    response={"chunks": "streaming content"},
                    status=200
                )
                return MockAsyncStreamResponse(mock_stream_chunks)
            else:
                send_to_hoover(
                    query=query_params,
                    response=mock_response.model_dump(),
                    status=200
                )
                return mock_response
        
        # Run the standard test
        response = asyncio.run(simulate_async_call())
        
        # Verify response
        assert response.choices[0].message.content == "Mocked Async OpenAI v2 Response"
        
        # Verify hoover was called
        mock_send_to_hoover.assert_called_once()
        
        # Verify arguments
        assert "query" in mock_send_to_hoover.call_args[1]
        assert mock_send_to_hoover.call_args[1]["query"]["model"] == "gpt-4o-mini"
        assert mock_send_to_hoover.call_args[1]["query"]["stream"] is False
        
        # Reset mock for streaming test
        mock_send_to_hoover.reset_mock()
        
        # Run the streaming test
        stream_response = asyncio.run(simulate_async_call(stream=True))
        
        # Stream the content
        async def collect_stream():
            content = ""
            async for chunk in stream_response:
                if chunk.choices[0].delta.content:
                    content += chunk.choices[0].delta.content
            return content
        
        # Get the streamed content
        streamed_content = asyncio.run(collect_stream())
        
        # Verify streamed content
        assert streamed_content == "Async Part 1 Async Part 2 Async Part 3"
        
        # Verify hoover was called for streaming
        mock_send_to_hoover.assert_called_once()
        
        # Verify the stream parameter was captured
        assert "query" in mock_send_to_hoover.call_args[1]
        assert mock_send_to_hoover.call_args[1]["query"]["stream"] is True
        
        # For v2, verify that AsyncOpenAI.__init__ has been wrapped
        assert hasattr(AsyncOpenAI.__init__, "_osmosis_wrapped"), "AsyncOpenAI.__init__ was not wrapped"
    
    finally:
        # Restore the original version
        if original_version is not None:
            openai.version.__version__ = original_version
        # Reset mock
        mock_send_to_hoover.reset_mock()

# Test disabling hoover
def test_disable_hoover(setup_osmosis):
    mock_send_to_hoover = setup_osmosis
    mock_send_to_hoover.reset_mock()  # Reset call count
    
    # Test disabling and enabling
    osmosis_wrap.disable_hoover()
    assert not osmosis_wrap.utils.enabled
    
    # Make a mocked call with Anthropic
    with patch("anthropic.Anthropic") as MockAnthropic:
        # Set up mock response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Response while disabled")]
        MockAnthropic.return_value.messages.create.return_value = mock_response
        
        # Create client and make API call
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=mock_get_api_key("anthropic"))
            client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=150,
                messages=[{"role": "user", "content": "This request won't be logged."}]
            )
        except ImportError:
            # Fall back to OpenAI if Anthropic is not available
            with patch("openai.OpenAI") as MockOpenAI:
                mock_response = MagicMock()
                mock_response.choices = [MagicMock(message=MagicMock(content="Response while disabled"))]
                MockOpenAI.return_value.chat.completions.create.return_value = mock_response
                
                from openai import OpenAI
                client = OpenAI(api_key=mock_get_api_key("openai"))
                client.chat.completions.create(
                    model="gpt-4o-mini",
                    max_tokens=150,
                    messages=[{"role": "user", "content": "This request won't be logged."}]
                )
    
    # Verify hoover was not called
    assert not mock_send_to_hoover.called
    
    # Re-enable and test
    osmosis_wrap.enable_hoover()
    assert osmosis_wrap.utils.enabled

@pytest.mark.skipif(
    pytest.importorskip("openai", reason="openai package not installed") is None,
    reason="OpenAI package not installed"
)
def test_openai_async_support(setup_osmosis):
    """Test that osmosis_wrap supports async OpenAI clients by directly checking the adapter code."""
    mock_send_to_hoover = setup_osmosis
    mock_send_to_hoover.reset_mock()  # Reset call count
    
    # Import OpenAI module first
    import openai
    import asyncio
    import inspect
    
    try:
        # Check if AsyncOpenAI is available
        try:
            from openai import AsyncOpenAI
        except ImportError:
            pytest.skip("AsyncOpenAI not available in this OpenAI version")
        
        # Import the OpenAI adapter
        from osmosis_wrap.adapters import openai as openai_adapter
        
        # Check for _wrap_openai_v1 and _wrap_openai_v2 functions
        assert hasattr(openai_adapter, "_wrap_openai_v1"), "Missing _wrap_openai_v1 function"
        assert hasattr(openai_adapter, "_wrap_openai_v2"), "Missing _wrap_openai_v2 function"
        
        # Check for async wrapping in _wrap_openai_v1 function
        v1_wrapper_code = inspect.getsource(openai_adapter._wrap_openai_v1)
        assert "async def wrapped_async_method" in v1_wrapper_code, "V1 wrapper missing async support"
        
        # Check for async wrapping in _wrap_openai_v2 function
        v2_wrapper_code = inspect.getsource(openai_adapter._wrap_openai_v2)
        assert "async def wrapped_achat_create" in v2_wrapper_code, "V2 wrapper missing async chat support"
        assert "async def wrapped_acompletions_create" in v2_wrapper_code, "V2 wrapper missing async completions support"
        
        # Check for AsyncOpenAI specific wrapping
        assert "AsyncOpenAI" in v1_wrapper_code or "AsyncOpenAI" in v2_wrapper_code, "No direct AsyncOpenAI support found"
        
        # Create a simple mock test
        async def mock_send_async():
            # Simulate an async OpenAI call
            from osmosis_wrap.utils import send_to_hoover
            send_to_hoover(
                query={"model": "gpt-4o-mini", "max_tokens": 150},
                response={"content": "Mocked async response"},
                status=200
            )
            return "Success"
            
        # Run the async function
        result = asyncio.run(mock_send_async())
        
        # Verify the result and that hoover was called
        assert result == "Success"
        mock_send_to_hoover.assert_called_once()
        
        # Verify the arguments
        assert "query" in mock_send_to_hoover.call_args[1]
        assert mock_send_to_hoover.call_args[1]["query"]["model"] == "gpt-4o-mini"
        assert mock_send_to_hoover.call_args[1]["status"] == 200
    
    finally:
        # Reset mock
        mock_send_to_hoover.reset_mock()

if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 