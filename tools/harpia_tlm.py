"""
harpia_tlm.py — Protocolo de telemetria Harpia AeroDesign em Python.

Espelha lib/telemetry_protocol/telemetry_packet.h e frame_codec.h dos
firmwares e a função decodePacket() do Telemetry_App:

  * pacote de 1024 bits (128 bytes) — aba "Enlace" da planilha de projeto;
  * quadros seriais  A5 5A | tipo | comprimento | carga | CRC-16/CCITT-FALSE;
  * arquivos FLT_nnnn.BIN (placa de voo) e GND_nnnn.BIN (estação de solo).

Somente biblioteca padrão. Usado por decode_log.py e gen_demo_logs.py.
"""
from __future__ import annotations

import math
import struct
from typing import Dict, Iterator, List, Optional, Tuple

PROTOCOL_VERSION = 1
PACKET_SIZE = 128
HEADER_SIZE = 512
STATUS_SIZE = 48
STATUS_MAGIC = 0xA7

FT_TELEMETRY, FT_GS_STATUS, FT_FLIGHT_STATUS, FT_TEXT = 0x01, 0x02, 0x03, 0x10
RSSI_NA = -32768

F32_FIELDS = ["x", "y", "z", "phi", "theta", "psi", "xdot", "ydot", "zdot",
              "phidot", "thetadot", "psidot", "xddot", "yddot", "zddot",
              "phiddot", "thetaddot", "psiddot"]
PACKET_STRUCT = struct.Struct("<I18fhhHH22sBBBbBBHHhhhhhh")
assert PACKET_STRUCT.size == PACKET_SIZE

STATUS_STRUCT = struct.Struct("<BBBBIHHBBHHBBIIHHHHiii")
assert STATUS_STRUCT.size == STATUS_SIZE
STATUS_FIELDS = ["magic", "version", "state", "flags", "micros", "dev_present", "dev_fault",
                 "gnss_fix", "gnss_numsv", "gnss_hacc_cm", "sd_file_index", "sd_ring_pct", "op_mode",
                 "sd_records", "sd_dropped", "imu_exec_us_max", "imu_exec_us_avg", "tx_skipped",
                 "fw_build", "home_lat_e7", "home_lon_e7", "home_hmsl_mm"]

GS_STATUS_STRUCT = struct.Struct("<BBBBIIIIIIHHhh")
assert GS_STATUS_STRUCT.size == 36
GS_STATUS_FIELDS = ["version", "state", "flags", "op_mode", "uptime_ms", "rx_ok", "rx_crc_err",
                    "rx_lost_est", "usb_forwarded", "sd_bytes", "sd_file_index", "last_rx_age_ms",
                    "last_rssi_x10", "last_snr_x10"]
RXMETA_STRUCT = struct.Struct("<hhI")

FLIGHT_STATES = ["Boot", "Autoteste", "Calibracao", "Pronto", "Comunicacao", "Gravacao", "Degradado", "Depuracao"]
GS_STATES = ["Boot", "Autoteste", "Pronto", "Recepcao", "Recepcao com gravacao", "Sem enlace", "Degradado", "Depuracao"]
TXPWR_MW = [0, 10, 25, 100, 500, 1000, 2000, 250, 50]
FLX_LSB_V = 1.024 / 32768.0


# --------------------------------------------------------------------------- canais
def pack_channels(values: List[int]) -> bytes:
    """16 valores de 11 bits → 22 bytes (LSB primeiro, igual ao CRSF)."""
    acc = 0
    for i, v in enumerate(values[:16]):
        acc |= (int(v) & 0x7FF) << (11 * i)
    return acc.to_bytes(22, "little")


def unpack_channels(b: bytes) -> List[int]:
    acc = int.from_bytes(b[:22], "little")
    return [(acc >> (11 * i)) & 0x7FF for i in range(16)]


def crsf_to_us(v: int) -> float:
    return 1500.0 + (v - 992) * 0.625


def us_to_crsf(us: float) -> int:
    return max(0, min(2047, int(round(992 + (us - 1500.0) / 0.625))))


def _sat(v: float, lo: int, hi: int) -> int:
    if v != v:
        return 0
    return max(lo, min(hi, int(round(v))))


# --------------------------------------------------------------------------- pacote
def encode_packet(s: Dict) -> bytes:
    """Dicionário em unidades físicas (SI, rad, NED; canais em µs; tensões em V;
    correntes em A; deflexões em V) → 128 bytes."""
    ch = [us_to_crsf(s.get(f"ch{i+1}", 1500.0)) for i in range(16)]
    txpwr_mw = s.get("TXPWR", 100)
    txidx = min(range(len(TXPWR_MW)), key=lambda i: abs(TXPWR_MW[i] - txpwr_mw))
    return PACKET_STRUCT.pack(
        int(s.get("micros", 0)) & 0xFFFFFFFF,
        *[float(s.get(k, 0.0)) for k in F32_FIELDS],
        _sat(s.get("h", 0.0) / 0.1, -32768, 32767),
        _sat(s.get("T", 15.0) / 0.01, -32768, 32767),
        _sat(s.get("P", 101325.0) - 50000.0, 0, 65535),
        _sat(s.get("Vinf", 0.0) / 0.01, 0, 65535),
        pack_channels(ch),
        _sat(-s.get("RSSI1", -60), 0, 255), _sat(-s.get("RSSI2", -60), 0, 255),
        _sat(s.get("LQUL", 100), 0, 255), _sat(s.get("SNR", 10), -128, 127),
        txidx, _sat(s.get("LQDL", 100), 0, 255),
        _sat(s.get("Um", 0.0) / 0.001, 0, 65535), _sat(s.get("Uc", 0.0) / 0.001, 0, 65535),
        _sat(s.get("Im", 0.0) / 0.005, -32768, 32767), _sat(s.get("Ic", 0.0) / 0.005, -32768, 32767),
        *[_sat(s.get(f"flx{i+1}", 0.0) / FLX_LSB_V, -32768, 32767) for i in range(4)],
    )


def decode_packet(b: bytes, offset: int = 0) -> Dict:
    v = PACKET_STRUCT.unpack_from(b, offset)
    s: Dict = {"micros": v[0]}
    for i, k in enumerate(F32_FIELDS):
        s[k] = v[1 + i]
    s["h"] = v[19] * 0.1
    s["T"] = v[20] * 0.01
    s["P"] = v[21] + 50000.0
    s["Vinf"] = v[22] * 0.01
    for i, c in enumerate(unpack_channels(v[23])):
        s[f"ch{i+1}"] = crsf_to_us(c)
    s["RSSI1"], s["RSSI2"] = -v[24], -v[25]
    s["LQUL"], s["SNR"] = v[26], v[27]
    s["TXPWR"] = TXPWR_MW[v[28]] if v[28] < len(TXPWR_MW) else 0
    s["LQDL"] = v[29]
    s["Um"], s["Uc"] = v[30] * 0.001, v[31] * 0.001
    s["Im"], s["Ic"] = v[32] * 0.005, v[33] * 0.005
    for i in range(4):
        s[f"flx{i+1}"] = v[34 + i] * FLX_LSB_V
    return s


def encode_status(st: Dict) -> bytes:
    vals = [st.get(k, 0) for k in STATUS_FIELDS]
    vals[0] = STATUS_MAGIC
    vals[1] = PROTOCOL_VERSION
    return STATUS_STRUCT.pack(*vals)


def decode_status(b: bytes, offset: int = 0) -> Dict:
    return dict(zip(STATUS_FIELDS, STATUS_STRUCT.unpack_from(b, offset)))


def encode_gs_status(st: Dict) -> bytes:
    vals = [st.get(k, 0) for k in GS_STATUS_FIELDS]
    vals[0] = PROTOCOL_VERSION
    return GS_STATUS_STRUCT.pack(*vals)


def decode_gs_status(b: bytes, offset: int = 0) -> Dict:
    return dict(zip(GS_STATUS_FIELDS, GS_STATUS_STRUCT.unpack_from(b, offset)))


# --------------------------------------------------------------------------- quadros
def crc16_ccitt(data: bytes, crc: int = 0xFFFF) -> int:
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def encode_frame(ftype: int, payload: bytes) -> bytes:
    body = bytes([ftype, len(payload)]) + payload
    return b"\xA5\x5A" + body + struct.pack("<H", crc16_ccitt(body))


def iter_frames(data: bytes) -> Iterator[Tuple[int, bytes]]:
    """Percorre um fluxo de bytes e devolve (tipo, carga) dos quadros válidos."""
    i, n = 0, len(data)
    while i + 6 <= n:
        if data[i] != 0xA5 or data[i + 1] != 0x5A:
            i += 1
            continue
        ftype, ln = data[i + 2], data[i + 3]
        end = i + 4 + ln + 2
        if end > n:
            break
        body = data[i + 2:i + 4 + ln]
        if crc16_ccitt(body) == struct.unpack_from("<H", data, i + 4 + ln)[0]:
            yield ftype, bytes(data[i + 4:i + 4 + ln])
            i = end
        else:
            i += 1


# --------------------------------------------------------------------------- arquivos
PACKET_LAYOUT = ("micros:u32;x:f32;y:f32;z:f32;phi:f32;theta:f32;psi:f32;"
                 "xdot:f32;ydot:f32;zdot:f32;phidot:f32;thetadot:f32;psidot:f32;"
                 "xddot:f32;yddot:f32;zddot:f32;phiddot:f32;thetaddot:f32;psiddot:f32;"
                 "h:i16*0.1;T:i16*0.01;P:u16+50000;Vinf:u16*0.01;ch1-16:u11x16;"
                 "RSSI1:u8;RSSI2:u8;LQUL:u8;SNR:i8;TXPWR:u8;LQDL:u8;"
                 "battprop:u16*0.001;battsis:u16*0.001;corrtprop:i16*0.005;corrtsis:i16*0.005;"
                 "flx1-4:i16*1.024/32768;frame:NED;angles:rad")


def flight_log_header(rate_hz: int, file_index: int = 1, home: Optional[Tuple[float, float, float]] = None,
                      baro_ref_pa: float = 101325.0, fw: str = "FDATU 1.0.0") -> bytes:
    h = bytearray(HEADER_SIZE)
    struct.pack_into("<8sHHHHHHI", h, 0, b"HRPFLT1\0", PROTOCOL_VERSION, HEADER_SIZE, PACKET_SIZE,
                     rate_hz, file_index, 0, 0)
    if home:
        struct.pack_into("<iiiB", h, 24, int(home[0] * 1e7), int(home[1] * 1e7), int(home[2] * 1000), 1)
    struct.pack_into("<f", h, 40, baro_ref_pa)
    h[44:60] = fw.encode()[:15].ljust(16, b"\0")
    h[60:84] = b"demo".ljust(24, b"\0")
    h[84:84 + len(PACKET_LAYOUT)] = PACKET_LAYOUT.encode()
    return bytes(h)


def ground_log_header(source: str = "Ground_Station", fw: str = "GS 1.0.0", start_ms: int = 0) -> bytes:
    h = bytearray(HEADER_SIZE)
    struct.pack_into("<8sHHIHH", h, 0, b"HRPGND1\0", PROTOCOL_VERSION, HEADER_SIZE, start_ms, 0, 0)
    h[20:36] = fw.encode()[:15].ljust(16, b"\0")
    h[36:52] = source.encode()[:15].ljust(16, b"\0")
    return bytes(h)


def read_log(path: str, decimate: int = 1):
    """Lê FLT_*.BIN ou GND_*.BIN. Retorna (tipo, cabeçalho, amostras, estados_voo, estados_solo)."""
    data = open(path, "rb").read()
    magic = data[:8]
    samples, fstat, gstat = [], [], []
    if magic == b"HRPFLT1\0":
        rate = struct.unpack_from("<H", data, 14)[0] or 2000
        hdr = {"tipo": "voo", "taxa_hz": rate,
               "home": struct.unpack_from("<iiiB", data, 24), "baro_ref_pa": struct.unpack_from("<f", data, 40)[0],
               "fw": data[44:60].split(b"\0")[0].decode(errors="replace")}
        n = (len(data) - HEADER_SIZE) // PACKET_SIZE
        for k in range(0, n, max(1, decimate)):
            samples.append(decode_packet(data, HEADER_SIZE + k * PACKET_SIZE))
        return "voo", hdr, samples, fstat, gstat
    start = HEADER_SIZE if magic == b"HRPGND1\0" else 0
    hdr = {"tipo": "solo"}
    if start:
        hdr["fonte"] = data[36:52].split(b"\0")[0].decode(errors="replace")
    k = 0
    for ftype, pl in iter_frames(data[start:]):
        if ftype == FT_TELEMETRY and len(pl) >= PACKET_SIZE:
            if k % max(1, decimate) == 0:
                s = decode_packet(pl)
                if len(pl) >= PACKET_SIZE + 8:
                    rssi, snr, gs_ms = RXMETA_STRUCT.unpack_from(pl, PACKET_SIZE)
                    s["lora_rssi"] = None if rssi == RSSI_NA else rssi / 10
                    s["lora_snr"] = None if rssi == RSSI_NA else snr / 10
                    s["gs_ms"] = gs_ms
                samples.append(s)
            k += 1
        elif ftype == FT_FLIGHT_STATUS and len(pl) >= STATUS_SIZE:
            fstat.append(decode_status(pl))
        elif ftype == FT_GS_STATUS and len(pl) >= 36:
            gstat.append(decode_gs_status(pl))
    return "solo", hdr, samples, fstat, gstat


def unwrap_micros(samples: List[Dict]) -> List[float]:
    """Tempo em segundos a partir do primeiro pacote (trata o estouro de 32 bits)."""
    out, base, prev = [], 0, None
    for s in samples:
        m = s["micros"]
        if prev is not None and m < prev and prev - m > 2 ** 31:
            base += 2 ** 32
        prev = m
        out.append((m + base) / 1e6)
    t0 = out[0] if out else 0.0
    return [t - t0 for t in out]


# --------------------------------------------------------------------- atmosfera
def air_density(p: float, t_c: float) -> float:
    return p / (287.053 * (t_c + 273.15))


def pressure_altitude(p: float) -> float:
    return 44330.77 * (1.0 - (p / 101325.0) ** 0.190263)


def density_altitude(rho: float) -> float:
    return 44330.77 * (1.0 - (rho / 1.225) ** 0.234969)


def deg(rad: float) -> float:
    return rad * 180.0 / math.pi
