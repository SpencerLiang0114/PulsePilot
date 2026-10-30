import numpy as np
import pytest

from pulsepilot.pulse import pulse_estimate


@pytest.mark.parametrize("bpm", [42, 60, 72, 90, 120, 150, 175])
@pytest.mark.parametrize("offset", [0, 4, 8])
def test_known_pulse_survives_noise_and_slow_lighting_drift(bpm, offset):
    t = offset + np.arange(300)/30
    signal = (np.sin(2*np.pi*bpm/60*t) + 2*np.sin(2*np.pi*.15*t)
              + .1*np.random.default_rng(1).normal(size=300))
    estimate, quality = pulse_estimate(signal)
    assert estimate == pytest.approx(bpm, abs=1)
    assert quality > .55


@pytest.mark.parametrize("signal", [np.zeros(300), np.ones(300), np.arange(299),
                                     np.full(300, np.nan), np.full(300, np.inf)])
def test_invalid_or_flat_windows_have_no_estimate(signal):
    assert pulse_estimate(signal) == (None, None)


@pytest.mark.parametrize("seed", range(10))
def test_broadband_noise_does_not_pass_display_quality(seed):
    _, quality = pulse_estimate(np.random.default_rng(seed).normal(size=300))
    assert quality < .35
