import pytest
from unittest.mock import AsyncMock, MagicMock
from beliefstate.config import TrackerConfig
from beliefstate.extractor import BeliefExtractor
from beliefstate.call import LLMResponse


@pytest.mark.asyncio
async def test_belief_extractor_batch_embeddings_success():
    config = TrackerConfig()

    mock_adapter = MagicMock()
    mock_adapter.generate = AsyncMock(
        return_value=LLMResponse(
            text='[{"subject": "USER", "predicate": "likes", "value": "Python", "confidence": 0.9}]',
            raw_response=None,
        )
    )
    mock_adapter.get_embeddings = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

    extractor = BeliefExtractor(adapter=mock_adapter, config=config)

    beliefs = await extractor.extract("I like Python", turn=1, source="user")
    assert len(beliefs) == 1
    assert beliefs[0].subject == "USER"
    assert beliefs[0].value == "Python"
    assert beliefs[0].embedding == [0.1, 0.2, 0.3]

    mock_adapter.generate.assert_called_once()
    mock_adapter.get_embeddings.assert_called_once_with(["USER likes Python"])


@pytest.mark.asyncio
async def test_belief_extractor_batch_embeddings_fallback():
    config = TrackerConfig()

    mock_adapter = MagicMock()
    mock_adapter.generate = AsyncMock(
        return_value=LLMResponse(
            text='[{"subject": "USER", "predicate": "likes", "value": "Python", "confidence": 0.9}]',
            raw_response=None,
        )
    )
    # Batch embeddings fail
    mock_adapter.get_embeddings = AsyncMock(side_effect=Exception("API limit exceeded"))
    # Fallback individual succeeds
    mock_adapter.get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])

    extractor = BeliefExtractor(adapter=mock_adapter, config=config)

    beliefs = await extractor.extract("I like Python", turn=1, source="user")
    assert len(beliefs) == 1
    assert beliefs[0].subject == "USER"
    assert beliefs[0].embedding == [0.1, 0.2, 0.3]

    mock_adapter.get_embeddings.assert_called_once()
    mock_adapter.get_embedding.assert_called_once_with("USER likes Python")


@pytest.mark.asyncio
async def test_belief_extractor_malformed_json():
    config = TrackerConfig()
    mock_adapter = MagicMock()
    mock_adapter.generate = AsyncMock(
        return_value=LLMResponse(text="Invalid JSON", raw_response=None)
    )

    extractor = BeliefExtractor(adapter=mock_adapter, config=config)
    beliefs = await extractor.extract("I like Python", turn=1, source="user")
    assert beliefs == []


@pytest.mark.asyncio
async def test_belief_extractor_prompt_routing():
    mock_adapter = MagicMock()
    mock_adapter.generate = AsyncMock(
        return_value=LLMResponse(
            text='[{"subject": "USER", "predicate": "likes", "value": "Python", "confidence": 0.9}]',
            raw_response=None,
        )
    )
    mock_adapter.get_embeddings = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

    # 1. Test user routing
    config = TrackerConfig()
    extractor = BeliefExtractor(adapter=mock_adapter, config=config)
    await extractor.extract("I like Python", turn=1, source="user")

    called_prompt = mock_adapter.generate.call_args[0][0].messages[0]["content"]
    assert "precise fact and decision extraction engine" in called_prompt
    assert "I like Python" in called_prompt

    mock_adapter.generate.reset_mock()

    # 2. Test assistant routing (universal prompt is same for both)
    await extractor.extract("I run on servers in Paris", turn=1, source="assistant")
    called_prompt_ast = mock_adapter.generate.call_args[0][0].messages[0]["content"]
    assert "precise fact and decision extraction engine" in called_prompt_ast
    assert "I run on servers in Paris" in called_prompt_ast

    mock_adapter.generate.reset_mock()

    # 3. Test legacy override with {response} template
    custom_config = TrackerConfig(extract_prompt_template="CUSTOM PROMPT {response}")
    extractor_custom = BeliefExtractor(adapter=mock_adapter, config=custom_config)
    await extractor_custom.extract("I like Python", turn=1, source="user")
    called_prompt_custom_user = mock_adapter.generate.call_args[0][0].messages[0][
        "content"
    ]
    assert called_prompt_custom_user == "CUSTOM PROMPT I like Python"

    mock_adapter.generate.reset_mock()

    # 4. Test legacy override with {conversation} template
    custom_config2 = TrackerConfig(
        extract_prompt_template="CUSTOM PROMPT {conversation}"
    )
    extractor_custom2 = BeliefExtractor(adapter=mock_adapter, config=custom_config2)
    await extractor_custom2.extract("I run on servers", turn=1, source="assistant")
    called_prompt_custom_ast = mock_adapter.generate.call_args[0][0].messages[0][
        "content"
    ]
    assert called_prompt_custom_ast == "CUSTOM PROMPT I run on servers"


@pytest.mark.asyncio
async def test_belief_extractor_post_filtering():
    config = TrackerConfig()
    mock_adapter = MagicMock()

    mock_adapter.generate = AsyncMock(
        return_value=LLMResponse(
            text="["
            '{"subject": "USER", "predicate": "prefers", "value": "Python", "confidence": 0.9, "source": "user", "source_quote": "I prefer Python"},'
            '{"subject": "assistant", "predicate": "prefers", "value": "TensorFlow", "confidence": 0.9, "source": "assistant", "source_quote": "I prefer TensorFlow"},'
            '{"subject": "USER", "predicate": "should consider", "value": "Redis", "confidence": 0.8, "source": "assistant", "source_quote": "You should consider Redis"},'
            '{"subject": "Redis", "predicate": "has", "value": "built-in persistence", "confidence": 0.9, "source": "assistant", "source_quote": "Redis has built-in persistence"},'
            '{"subject": "Cache", "predicate": "type", "value": "Memcached", "confidence": 0.95, "source": "assistant", "source_quote": "I will set up Memcached"}'
            "]",
            raw_response=None,
        )
    )
    mock_adapter.get_embeddings = AsyncMock(return_value=[[0.1] * 384] * 5)

    extractor = BeliefExtractor(adapter=mock_adapter, config=config)
    beliefs = await extractor.process_turn(
        user_message="I prefer Python",
        assistant_response="I will set up Memcached",
        session_id="test_session",
        turn=1,
    )

    assert len(beliefs) == 2

    assert beliefs[0].subject == "USER"
    assert beliefs[0].predicate == "prefers"
    assert beliefs[0].value == "Python"
    assert beliefs[0].source == "user"

    assert beliefs[1].subject == "Cache"
    assert beliefs[1].predicate == "type"
    assert beliefs[1].value == "Memcached"
    assert beliefs[1].source == "assistant"
