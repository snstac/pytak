"""Operator log levels control real worker output without changing root logging."""

import asyncio
import io
import logging
from configparser import ConfigParser

import pytest
import pytak


@pytest.fixture
def log_output(monkeypatch):
    logger = pytak.Worker._logger
    old_level = logger.level
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))
    monkeypatch.setattr(logger, "handlers", [handler])
    monkeypatch.setattr(logger, "disabled", False)
    monkeypatch.delenv("PYTAK_LOG_LEVEL", raising=False)
    logger.setLevel(logging.INFO)
    yield logger, handler, output
    logger.setLevel(old_level)


def make_worker(kind, config):
    async def construct():
        # Older asyncio.Queue versions need a current event loop at construction.
        if kind == "Worker":
            return pytak.Worker(asyncio.Queue(), config)
        return pytak.CLITool(config)

    return asyncio.run(construct())


@pytest.mark.parametrize("kind", ["Worker", "CLITool"])
@pytest.mark.parametrize("level", ["DEBUG", "info", "WARNING", " ERROR ", "CRITICAL"])
def test_ini_log_level_sets_logger_and_handler(log_output, kind, level):
    logger, handler, _ = log_output
    config = ConfigParser()
    config.read_dict({"pytak": {"PYTAK_LOG_LEVEL": level}})
    make_worker(kind, config["pytak"])
    expected = logging.getLevelName(level.strip().upper())
    assert logger.level == handler.level == expected


@pytest.mark.parametrize("kind", ["Worker", "CLITool"])
def test_error_level_suppresses_warnings_but_keeps_errors(log_output, kind):
    logger, handler, output = log_output
    handler.setLevel(logging.CRITICAL)
    root_level = logging.getLogger().level
    make_worker(kind, {"PYTAK_LOG_LEVEL": "ERROR", "DEBUG": "1"})
    logger.warning("queue warning")
    logger.error("connection error")
    logger.debug("debug detail")
    assert output.getvalue() == "ERROR:connection error\n"
    assert logging.getLogger().level == root_level


@pytest.mark.parametrize("kind", ["Worker", "CLITool"])
def test_environment_log_level_overrides_config(log_output, monkeypatch, kind):
    logger, handler, _ = log_output
    monkeypatch.setenv("PYTAK_LOG_LEVEL", "ERROR")
    make_worker(kind, {"PYTAK_LOG_LEVEL": "DEBUG"})
    assert logger.level == handler.level == logging.ERROR


@pytest.mark.parametrize("kind", ["Worker", "CLITool"])
@pytest.mark.parametrize("value", ["", "loud", "25"])
def test_invalid_log_level_is_an_actionable_config_error(log_output, kind, value):
    with pytest.raises(ValueError, match="PYTAK_LOG_LEVEL.*DEBUG.*CRITICAL"):
        make_worker(kind, {"PYTAK_LOG_LEVEL": value})


@pytest.mark.parametrize("kind", ["Worker", "CLITool"])
def test_absent_setting_keeps_existing_level(log_output, kind):
    logger, _, _ = log_output
    make_worker(kind, {})
    assert logger.level == logging.INFO


@pytest.mark.parametrize("kind", ["Worker", "CLITool"])
def test_debug_still_enables_debug_messages_without_explicit_level(log_output, kind):
    logger, _, output = log_output
    config = ConfigParser()
    config.read_dict({"pytak": {"DEBUG": "1"}})
    make_worker(kind, config["pytak"])
    logger.debug("debug detail")
    assert output.getvalue() == "DEBUG:debug detail\n"
