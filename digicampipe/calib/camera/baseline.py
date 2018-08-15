import numpy as np


def fill_dark_baseline(events, dark_baseline):

    for event in events:

        event.data.dark_baseline = dark_baseline

        yield event


def fill_baseline(events, baseline):

    for event in events:

        event.data.baseline = baseline

        yield event


def fill_digicam_baseline(events):

    for event in events:

        event.data.baseline = event.data.digicam_baseline

        yield event


def compute_baseline_with_min(events):

    for event in events:

        adc_samples = event.data.adc_samples
        event.data.baseline = np.min(adc_samples, axis=-1)

        yield event


def subtract_baseline(events):

    for event in events:

        baseline = event.data.baseline

        event.data.adc_samples = event.data.adc_samples.astype(baseline.dtype)
        event.data.adc_samples -= baseline[..., np.newaxis]

        yield event


def compute_baseline_shift(events):

    for event in events:

        event.data.baseline_shift = event.data.baseline \
                                    - event.data.dark_baseline

        yield event


def compute_nsb_rate(events, gain, pulse_area, crosstalk, bias_resistance,
                     cell_capacitance):

    for event in events:

        baseline_shift = event.data.baseline_shift
        nsb_rate = baseline_shift / (gain * pulse_area * (1 + crosstalk) -
                                     baseline_shift * bias_resistance *
                                     cell_capacitance)
        event.data.nsb_rate = nsb_rate

        yield event


def compute_gain_drop(events, bias_resistance, cell_capacitance):

    for event in events:

        nsb_rate = event.data.nsb_rate
        gain_drop = 1. / (1. + nsb_rate * cell_capacitance
                          * bias_resistance * 1E9)

        event.data.gain_drop = gain_drop

        yield event
