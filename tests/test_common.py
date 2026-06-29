"""Tests for beliefstate.integrations.common (IntegrationLogger, validate_session_id)."""

import pytest
from beliefstate.integrations.common import IntegrationLogger, validate_session_id


class TestIntegrationLogger:
    def test_init(self):
        log = IntegrationLogger("test.module", "TestType")
        assert log.integration_type == "TestType"

    def test_debug(self, caplog):
        import logging

        log = IntegrationLogger("test.module", "TestType")
        with caplog.at_level(logging.DEBUG, logger="test.module"):
            log.debug("test_op", key="value")
        assert any("[TestType] test_op" in r.message for r in caplog.records)

    def test_info(self, caplog):
        import logging

        log = IntegrationLogger("test.module", "TestType")
        with caplog.at_level(logging.INFO, logger="test.module"):
            log.info("test_op")
        assert any("[TestType] test_op" in r.message for r in caplog.records)

    def test_warning(self, caplog):
        import logging

        log = IntegrationLogger("test.module", "TestType")
        with caplog.at_level(logging.WARNING, logger="test.module"):
            log.warning("test_op")
        assert any("[TestType] test_op" in r.message for r in caplog.records)

    def test_error(self, caplog):
        import logging

        log = IntegrationLogger("test.module", "TestType")
        with caplog.at_level(logging.ERROR, logger="test.module"):
            log.error("test_op")
        assert any("[TestType] test_op" in r.message for r in caplog.records)


class TestValidateSessionId:
    def test_valid(self):
        assert validate_session_id("my-session") == "my-session"

    def test_strips_whitespace(self):
        assert validate_session_id("  session  ") == "session"

    def test_empty_string(self):
        with pytest.raises(ValueError, match="non-empty"):
            validate_session_id("")

    def test_none(self):
        with pytest.raises(ValueError, match="non-empty"):
            validate_session_id(None)

    def test_whitespace_only(self):
        with pytest.raises(ValueError, match="non-empty"):
            validate_session_id("   ")

    def test_non_string(self):
        with pytest.raises(ValueError, match="non-empty"):
            validate_session_id(123)
