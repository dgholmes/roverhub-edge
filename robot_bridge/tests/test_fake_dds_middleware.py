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
    middleware.publish("rt/leds/cmd", cmd)
    assert middleware.published["rt/leds/cmd"][-1] is cmd
    assert middleware.published["rt/leds/cmd"][-1].leds()[0].name() == "leg_light1"


def test_middleware_records_published_voice_cmd():
    middleware = FakePyDDSMiddleware(0)
    middleware.createVoiceCmdWriter("rt/voice/cmd", {})
    voice = FakeVoiceCmd()
    voice.header(FakeHeader())
    voice.file_path("/tmp/clip.wav")
    middleware.publish("rt/voice/cmd", voice)
    assert middleware.published["rt/voice/cmd"][-1].file_path() == "/tmp/clip.wav"
