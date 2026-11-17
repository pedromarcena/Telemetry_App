# Protocolo de telemetria Harpia (versão 1)

Documento comum aos repositórios **Flight_Data_Acquisition_and_Transmission_Unit**, **Ground_Station** e **Telemetry_App**. A referência executável é `lib/telemetry_protocol/telemetry_packet.h` (firmwares), `tools/harpia_tlm.py` (Python) e `decodePacket()` em `index.html` (aplicativo). Os três são verificados entre si: o pacote montado em C++ é decodificado em Python e recodificado byte a byte idêntico.

## 1. Pacote de dados — 1024 bits (128 bytes)

Composição e ordem da aba **Enlace** da planilha de pinagem do projeto. Little-endian, bit menos significativo primeiro; com isso todos os campos de 8, 16 e 32 bits ficam alinhados a byte e o bloco de canais tem o mesmo empacotamento do quadro `RC_CHANNELS_PACKED` do CRSF.

| Byte | Campo | Bits | Tipo | Unidade / escala |
|---:|---|---:|---|---|
| 0 | `micros` | 32 | uint32 | µs desde a partida (esp_timer), estoura a cada 71,6 min |
| 4 | `x`, `y`, `z` | 3 × 32 | float | m — posição NED em relação à origem (norte, leste, para baixo); `z = −h` |
| 16 | `phi`, `theta`, `psi` | 3 × 32 | float | rad — ângulos de Euler ZYX (rolamento, arfagem, guinada), corpo FRD |
| 28 | `xdot`, `ydot`, `zdot` | 3 × 32 | float | m/s — velocidade NED (`zdot` positivo para baixo) |
| 40 | `phidot`, `thetadot`, `psidot` | 3 × 32 | float | rad/s — taxas dos ângulos de Euler |
| 52 | `xddot`, `yddot`, `zddot` | 3 × 32 | float | m/s² — aceleração cinemática NED, sem a gravidade |
| 64 | `phiddot`, `thetaddot`, `psiddot` | 3 × 32 | float | rad/s² — acelerações angulares |
| 76 | `h` | 16 | int16 | 0,1 m — altitude acima da referência barométrica (decolagem) |
| 78 | `T` | 16 | int16 | 0,01 °C — temperatura do BMP390 |
| 80 | `P` | 16 | uint16 | Pa − 50 000 — pressão estática absoluta (50,000 a 115,535 kPa, 1 Pa) |
| 82 | `Vinf` | 16 | uint16 | 0,01 m/s — velocidade verdadeira do escoamento (Pitot) |
| 84 | `ch1` … `ch16` | 16 × 11 | bits | valor CRSF de 11 bits; µs = 1500 + (v − 992) × 0,625 |
| 106 | `RSSI1`, `RSSI2` | 2 × 8 | uint8 | −dBm — RSSI das antenas do ER8 (enlace de subida) |
| 108 | `LQUL` | 8 | uint8 | % — qualidade do enlace de subida |
| 109 | `SNR` | 8 | int8 | dB — SNR do enlace de subida |
| 110 | `TXPWR` | 8 | uint8 | índice CRSF: 0, 10, 25, 100, 500, 1000, 2000, 250, 50 mW |
| 111 | `LQDL` | 8 | uint8 | % — qualidade do enlace de descida (telemetria ELRS) |
| 112 | `battprop` | 16 | uint16 | mV — U_m, bateria do grupo motopropulsor |
| 114 | `battsis` | 16 | uint16 | mV — U_c, bateria do sistema de comando |
| 116 | `corrtprop` | 16 | int16 | 5 mA — I_m (±163,8 A) |
| 118 | `corrtsis` | 16 | int16 | 5 mA — I_c |
| 120 | `flx1` … `flx4` | 4 × 16 | int16 | código bruto do ADS1115 U4 (PGA ±1,024 V → 31,25 µV/LSB) |

Observações de projeto:

- **P** é a pressão estática absoluta do BMP390. O requisito R.F.6 do TG fala em “pressão manométrica”; a absoluta foi escolhida porque é ela que permite calcular densidade do ar, altitude-pressão, altitude-densidade e velocidade indicada.
- As **deflexões** são transmitidas como tensão bruta: a calibração dos sensores flexíveis é trabalho futuro, e guardar o dado bruto permite recalibrar o voo inteiro depois. O aplicativo converte em graus com os parâmetros do menu Ajustes.
- A resolução de corrente (5 mA) é melhor que os 10 mA de R.E.4 e que a resolução da própria cadeia de medição (≈ 7,6 mA por LSB no ADS1115).

## 2. Pacote de estado da placa de voo — 48 bytes (LoRa, 1 Hz)

Enviado logo após um pacote de dados, uma vez por segundo; a estação o distingue pelo comprimento (48 ≠ 128) e pelo byte mágico `0xA7`.

| Byte | Campo | Tipo | Conteúdo |
|---:|---|---|---|
| 0 | magic | uint8 | `0xA7` |
| 1 | version | uint8 | versão do protocolo |
| 2 | state | uint8 | 0 Boot, 1 Autoteste, 2 Calibração, 3 Pronto, 4 Comunicação, 5 Gravação, 6 Degradado, 7 Depuração |
| 3 | flags | uint8 | bit0 gravando, bit1 origem GNSS definida, bit2 calibrado, bit3 saída USB ativa |
| 4 | micros | uint32 | mesmo relógio do pacote de dados |
| 8 | dev_present | uint16 | dispositivos que passaram no autoteste (bits abaixo) + bit11 fix 3D |
| 10 | dev_fault | uint16 | falhas confirmadas no momento |
| 12 | gnss_fix, gnss_numsv | 2 × uint8 | tipo de fix UBX e satélites |
| 14 | gnss_hacc_cm | uint16 | precisão horizontal |
| 16 | sd_file_index | uint16 | número do arquivo FLT_nnnn.BIN |
| 18 | sd_ring_pct, op_mode | 2 × uint8 | ocupação do buffer PSRAM, modo lembrado |
| 20 | sd_records, sd_dropped | 2 × uint32 | registros gravados e descartados |
| 28 | imu_exec_us_max, imu_exec_us_avg | 2 × uint16 | tempo de execução da tarefa IMU no último segundo (R.P.2: < 500 µs) |
| 32 | tx_skipped, fw_build | 2 × uint16 | pacotes não transmitidos (rádio ocupado), compilação |
| 36 | home_lat_e7, home_lon_e7, home_hmsl_mm | 3 × int32 | origem do referencial NED |

Bits de dispositivo: 0 BMI088-acelerômetro, 1 BMI088-giroscópio, 2 BMP390, 3 MMC5603, 4 MS4525DO, 5 ADS1115 U3, 6 ADS1115 U4, 7 NEO-M9N, 8 ER8 (CRSF), 9 E28, 10 microSD, 11 GNSS com fix 3D.

## 3. Quadros na porta serial

Usados pela estação de solo (USB nativa → aplicativo) e pela placa de voo em bancada (UART0 → conversor USB do kit, 921 600 baud):

```
A5 5A | tipo (1) | comprimento (1) | carga (comprimento) | CRC16 (2, little-endian)
CRC-16/CCITT-FALSE: polinômio 0x1021, valor inicial 0xFFFF, sobre tipo + comprimento + carga
```

| Tipo | Carga |
|---|---|
| `0x01` telemetria | pacote de 128 B + RxMeta de 8 B |
| `0x02` estado da estação | 36 B (estado, contadores de recepção, perdas estimadas, cartão, RSSI/SNR) |
| `0x03` estado da placa de voo | pacote de estado de 48 B + RxMeta de 8 B |
| `0x10` texto | ASCII |

`RxMeta`: `int16 rssi_x10` (0,1 dBm; −32768 quando o pacote veio por cabo), `int16 snr_x10` (0,1 dB), `uint32 gs_ms` (relógio da estação). Bytes fora de quadros são texto de console (linhas terminadas em `\n`); o aplicativo os mostra no painel Console.

Comandos de texto aceitos pela estação (terminados em `\n`): `MODE REC`, `MODE RX`, `STATUS`, `PING`. A placa de voo aceita no console: `status`, `raw`, `magcal`, `reboot`.

## 4. Arquivos de registro

Cabeçalho de 512 bytes (um setor do cartão), seguido dos dados:

- **FLT_nnnn.BIN** (placa de voo): `"HRPFLT1\0"`, versão, tamanho do cabeçalho, tamanho do registro (128), taxa (2000 Hz), índice, `micros` inicial, origem GNSS, pressão de referência barométrica, versão do firmware e descrição textual do layout. Depois, registros de 128 bytes contíguos (4 por setor).
- **GND_nnnn.BIN** (estação) e **sessao_*.BIN** (gravado pelo aplicativo): `"HRPGND1\0"`, versão, tamanho do cabeçalho, instante inicial, fonte. Depois, o mesmo fluxo de quadros da porta serial.

`tools/decode_log.py` converte os dois tipos em CSV; o aplicativo abre os dois no modo replay.

## 5. Enlace de rádio

| Parâmetro | Valor |
|---|---|
| Modulação | LoRa, 2440 MHz, BW 1625 kHz, SF5, CR 4/5, preâmbulo 12, CRC ligado, palavra de sincronismo 0x12 |
| Taxa de bits | 5 × 1 625 000 / 2⁵ × 4/5 ≈ 203 kbit/s |
| Tempo no ar | ≈ 5,7 ms (128 B) e ≈ 2,6 ms (48 B) — valores exatos impressos no autoteste pela RadioLib |
| Cadência | 100 pacotes de dados/s (1 a cada 20 registros de 2 kHz) + 1 pacote de estado/s |
