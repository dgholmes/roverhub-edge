from fake_dds_middleware import FakeHeader, FakeLedsCmd, FakeLEDControl, FakePyDDSMiddleware, FakeVoiceCmd


def test_middleware_records_created_writers():
    middleware = FakePyDDSMiddleware(0)
    middleware.createLedsCmdWriter("rt/leds/cmd", {"reliability": "reliable"})
    assert "rt/leds/cmd" in middleware.created_writers


def test_middleware_records_published_leds_cmd():
    middleware = FakePyDDSMiddleware(0)
    middleware.createLedsCmdWriter("rt/leds/cmd", {})
    led = FakeLEDControl()
    led.name("leg_light1")
    led.r(255)
    led.g(0)
    led.b(0)
    led.brightness(255)
    led.priority(0)
    cmd = FakeLedsCmd()
    cmd.leds([led])
    middleware.publishLedsCmd(cmd)
    assert middleware.published["rt/leds/cmd"][-1] is cmd
    assert middleware.published["rt/leds/cmd"][-1].leds()[0].name() == "leg_light1"


def test_middleware_records_published_voice_cmd():
    middleware = FakePyDDSMiddleware(0)
    middleware.createVoiceCmdWriter("rt/voice/cmd", {})
    voice = FakeVoiceCmd()
    voice.header(FakeHeader())
    voice.priority(0)
    voice.task_id("roverhub")
    voice.type("file")
    voice.path("/tmp/clip.wav")
    voice.data([])
    voice.flag(False)
    middleware.publishVoiceCmd(voice)
    assert middleware.published["rt/voice/cmd"][-1].path() == "/tmp/clip.wav"
