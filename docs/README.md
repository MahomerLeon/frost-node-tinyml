# Documentation

| Document | Contents | Requirement |
|---|---|---|
| [IEEE_proposal_frost_node.pdf](IEEE_proposal_frost_node.pdf) | Project proposal, IEEE conference format, 3 pages | R8 |
| [hardware_setup.md](hardware_setup.md) | How to connect every part, step by step, with a check after each step | — |
| [wiring_diagram_esp32s3.png](wiring_diagram_esp32s3.png) | Wiring diagram of the node (labels in Spanish) | — |
| [wiring_diagram_pico.png](wiring_diagram_pico.png) | Wiring diagram of the Raspberry Pi Pico used for the comparison | R7 |
| [wiring_diagram_both.png](wiring_diagram_both.png) | Complete current setup: ESP32-S3 with BME280, INA219 and DS18B20 probe, and the Pico alone, both connected to the PC | R7 |
| [capture_protocol.md](capture_protocol.md) | How the own dataset is captured, labeled, versioned and split | R4 |
| [data_structures.md](data_structures.md) | Circular buffer and hash table, with their complexity | R6 |
| [resource_report.md](resource_report.md) | How Flash, RAM, latency, CPU and power are measured; ESP32-S3 vs. Pico; results | R7 |

Still pending: the comparison of F1 between the float and the int8 model
(R3), which needs a real dataset and model.
