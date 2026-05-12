# BCI Taxonomy

Use this reference to classify candidate papers and avoid off-topic selections.

## Include

### Invasive BCI

- Intracortical arrays
- Utah array, Neuropixels-like implants, microelectrode arrays
- Motor decoding for cursor, robotic arm, typing, handwriting, or speech
- Long-term implant stability and closed-loop control

### Semi-Invasive And Surface Cortical BCI

- ECoG, sEEG, cortical surface arrays
- Speech neuroprosthesis
- Decoding intended speech, handwriting, movement, or affective state

### Non-Invasive BCI

- EEG, MEG, fNIRS, ultrasound or other non-invasive neural sensing
- Motor imagery, SSVEP, P300, attention, fatigue, workload
- Real-time control, assistive communication, rehabilitation

### Stimulation And Closed-Loop Systems

- DBS, cortical stimulation, spinal stimulation paired with neural decoding
- Adaptive stimulation for movement, mood, epilepsy, tremor, or restoration
- Bidirectional BCI with sensory feedback

### Methods Worth Covering

- Neural decoding foundation models
- Cross-session/domain adaptation
- Low-latency online decoding
- Data-efficient calibration
- Human-in-the-loop learning
- Safety, robustness, implant longevity, privacy

## Exclude Or Deprioritize

- Generic neuroscience without a control/communication/restoration interface.
- Generic ML on brain data with no BCI use case or neural interface implication.
- Pure consumer EEG wellness claims without rigorous validation.
- Animal-only papers unless they clearly change the BCI roadmap.
- Reviews unless the user requests a roundup.

## Classification Labels

Use one or more:

```text
invasive-bci
ecog-seeg
noninvasive-eeg
speech-decoding
motor-decoding
closed-loop-stimulation
sensory-feedback
rehabilitation
clinical-translation
algorithm-method
dataset-benchmark
ethics-safety
```

## Importance Signals

Strong signals:

- First-in-human, large patient cohort, or clinically meaningful endpoint.
- Major speed/accuracy/reliability improvement in online BCI.
- Direct comparison against established baselines.
- Open dataset/code that may reshape the field.
- Nature, Science, Cell, NEJM, Lancet, Neuron, Nature Neuroscience, Nature Biomedical Engineering, Nature Machine Intelligence, Science Translational Medicine, PNAS, Brain, JNE, IEEE TNSRE.

Weak signals:

- Offline-only decoding with small private dataset and no strong baseline.
- Overstated claims from limited EEG classification.
- Accuracy-only improvements without usability, latency, or robustness analysis.
