"""Ten-second spectral pulse estimation on completed FacePhys output."""
import numpy as np
from scipy.signal import butter, detrend, sosfiltfilt, welch


def pulse_estimate(values, fps=30):
    signal = np.asarray(values, dtype=float)
    if signal.ndim != 1 or len(signal) < round(10*fps) or not np.isfinite(signal).all():
        return None, None
    signal = detrend(signal)
    if np.std(signal) < 1e-8:
        return None, None
    signal = sosfiltfilt(butter(3, [.5, 3], fs=fps, btype="bandpass", output="sos"), signal)
    # Use the full window, without upstream's peak-by-peak amplitude reshaping.
    frequencies, power = welch(signal, fs=fps, nperseg=len(signal), nfft=8192)
    band = (frequencies >= 40/60) & (frequencies <= 180/60)
    frequency = frequencies[band][np.argmax(power[band])]
    # Quality must agree with the selected pulse period, on the same filtered signal.
    signal -= signal.mean()
    correlation = np.correlate(signal, signal, mode="full")[len(signal)-1:]
    if correlation[0] <= 1e-12:
        return None, None
    lag = round(fps/frequency)
    quality = np.max(correlation[max(1, lag-1):lag+2])/correlation[0]
    return float(frequency*60), float(np.clip(quality, 0, 1))
