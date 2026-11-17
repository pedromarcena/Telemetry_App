#!/usr/bin/env python3
"""
gen_demo_logs.py — Gera arquivos de demonstração para o modo replay do
Telemetry_App a partir de um voo simulado (decolagem, subida, circuito com
curvas de 30°, descida e pouso, com vento de 3 m/s):

  samples/demo_voo_FLT_0001.BIN    registro da placa de voo (cabeçalho + pacotes de 128 B)
  samples/demo_solo_GND_0001.BIN   registro da estação de solo (quadros com RSSI/SNR,
                                   perdas aleatórias e uma queda de enlace de 3 s)
  samples/demo_simulador.csv       formato legado do simulador (t, phi, theta, psi, ...)

    python tools/gen_demo_logs.py [--taxa-voo 200] [--duracao 120]
"""
import argparse
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harpia_tlm as h  # noqa: E402

G = 9.80665
D2R = math.pi / 180.0
FIELD_ELEV = 760.0          # m (São Paulo)
WIND_FROM = 135.0 * D2R     # vento de sudeste
WIND_SPD = 3.0
HOME = (-23.6418, -46.5264, FIELD_ELEV)


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def simulate(rate, dur, seed=7):
    rnd = random.Random(seed)
    dt = 1.0 / rate
    wN, wE = -WIND_SPD * math.cos(WIND_FROM), -WIND_SPD * math.sin(WIND_FROM)
    N = E = hgt = 0.0
    V = 0.0
    psi = 60 * D2R
    phi = gam = 0.0
    theta = 0.0
    phi_r = gam_r = 0.0          # comandos com taxa limitada
    alpha = 0.0
    landed = False
    acc_f = [0.0, 0.0, 0.0]
    wind_k = 0.0
    racc_f = [0.0, 0.0, 0.0]
    Qm = Qc = 0.0
    prev = None
    out = []
    for k in range(int(dur * rate)):
        t = k * dt
        # ---------------- fases do voo
        if t < 10:
            phase, Vt, thr, gam_c, psi_c = "parado", 0, 0.0, 0, 60 * D2R
        elif t < 16.5:
            phase, Vt, thr, gam_c, psi_c = "corrida", 16, 1.0, 0, 60 * D2R
        elif t < 34:
            phase, Vt, thr, gam_c, psi_c = "subida", 16, 0.85, 7 * D2R, 60 * D2R
        elif t < dur - 52:
            leg = int((t - 34) // 21) % 2
            psi_c = (60 if leg == 0 else 240) * D2R
            phase, Vt, thr = "circuito", 18, 0.55
            gam_c = max(-5 * D2R, min(5 * D2R, 0.03 * (60 - hgt)))
        elif not landed:
            phase, Vt, thr, psi_c = "descida", 15, 0.15, 60 * D2R
            gam_c = -6 * D2R if hgt > 4 else -1.5 * D2R          # arredondamento antes do toque
            if hgt <= 0.05 and t > dur - 45:
                landed = True
        else:
            phase, Vt, thr, gam_c, psi_c = "pouso", 0, 0.0, 0, psi
        on_ground = phase in ("parado", "corrida", "pouso")
        if phase == "corrida" and V > 13.5:
            on_ground = False
        # ---------------- dinâmica simplificada
        V += (Vt - V) / (2.5 if phase != "pouso" else 1.5) * dt
        V = max(V, 0.0)
        if on_ground:
            phi_c, gam_c = 0.0, 0.0
        else:
            phi_c = max(-30 * D2R, min(30 * D2R, 2.0 * wrap(psi_c - psi)))
        # limita a taxa dos comandos (rolamento 60 °/s, trajetória 8 °/s)
        phi_r += max(-60 * D2R * dt, min(60 * D2R * dt, phi_c - phi_r))
        gam_r += max(-8 * D2R * dt, min(8 * D2R * dt, gam_c - gam_r))
        gam += (gam_r - gam) * dt / (0.3 if on_ground else 1.2)
        phi += (phi_r - phi) * dt / 0.4
        if not on_ground and V > 3:
            psi = wrap(psi + G * math.tan(phi) / V * dt)
        alpha_c = 0.0 if on_ground else (4.0 * D2R + 0.04 * (1 / max(math.cos(phi), 0.5) - 1))
        alpha += max(-10 * D2R * dt, min(10 * D2R * dt, alpha_c - alpha))
        theta_c = gam + alpha
        theta += (theta_c - theta) * dt / 0.3
        # velocidades
        van, vae = V * math.cos(gam) * math.cos(psi), V * math.cos(gam) * math.sin(psi)
        wind_k += ((0.0 if on_ground else 1.0) - wind_k) * dt / 1.0   # o vento atua aos poucos após a decolagem
        vn, ve = van + wind_k * wN, vae + wind_k * wE
        vz_up = V * math.sin(gam) if not on_ground else 0.0
        N += vn * dt
        E += ve * dt
        hgt = max(0.0, hgt + vz_up * dt)
        if hgt <= 0.0:
            vz_up = min(vz_up, 0.0) if hgt > 0 else 0.0
        # derivadas numéricas
        cur = (vn, ve, -vz_up, phi, theta, psi)
        if prev is None:
            prev = cur
            prev_rates = (0.0, 0.0, 0.0)
        a_raw = [(c - p) / dt for c, p in zip(cur[:3], prev[:3])]
        rates = ((phi - prev[3]) / dt, (theta - prev[4]) / dt, wrap(psi - prev[5]) / dt)
        racc_raw = [(r - pr) / dt for r, pr in zip(rates, prev_rates)]
        prev, prev_rates = cur, rates
        # passa-baixa de saída (τ = 30 ms), como o filtro de saída do firmware
        kf = 1 - math.exp(-dt / 0.03)
        acc_f = [a + kf * (r - a) for a, r in zip(acc_f, a_raw)]
        racc_f = [a + kf * (r - a) for a, r in zip(racc_f, racc_raw)]
        aN, aE, aD = acc_f
        racc = racc_f
        # ---------------- comandos e superfícies
        da = max(-20, min(20, 40 * (phi_r - phi) / D2R / 30 + 4 * (phi_c - phi_r) / D2R / 30))
        de = max(-20, min(20, -2 + 1.5 * (gam_r - gam) / D2R))
        dr = 0.25 * da
        # ---------------- elétrica
        Im = 1.5 + 48 * thr ** 1.5 + rnd.gauss(0, 0.15)
        Ic = 0.6 + 0.04 * (abs(da) + abs(de)) + rnd.gauss(0, 0.02)
        Qm += Im * dt / 3.6
        Qc += Ic * dt / 3.6
        Um = 25.0 - 0.022 * Im - 1.8 * Qm / 2200 + rnd.gauss(0, 0.005)
        Uc = 6.68 - 0.03 * Ic - 0.2 * Qc / 1100 + rnd.gauss(0, 0.003)
        # ---------------- atmosfera e enlaces
        alt = FIELD_ELEV + hgt
        P = 101325.0 * (1 - alt / 44330.77) ** (1 / 0.190263) + rnd.gauss(0, 1.2)
        T = 27.0 - 0.0065 * hgt + rnd.gauss(0, 0.03)
        rho = P / (287.053 * (T + 273.15))
        tas = V if not on_ground else V
        d = math.hypot(N, E)
        rssi = -38 - 20 * math.log10(max(d, 5) / 5) + rnd.gauss(0, 1.5)
        lq = 100 if rnd.random() > 0.03 else rnd.randint(85, 99)
        s = {
            "micros": int(5_000_000 + t * 1e6) & 0xFFFFFFFF,
            "x": N, "y": E, "z": -hgt,
            "phi": phi + rnd.gauss(0, 0.002), "theta": theta + rnd.gauss(0, 0.002), "psi": psi,
            "xdot": vn, "ydot": ve, "zdot": -vz_up,
            "phidot": rates[0], "thetadot": rates[1], "psidot": rates[2],
            "xddot": aN, "yddot": aE, "zddot": aD,
            "phiddot": racc[0], "thetaddot": racc[1], "psiddot": racc[2],
            "h": hgt, "T": T, "P": P, "Vinf": tas if tas > 2.2 else 0.0,
            "RSSI1": rssi, "RSSI2": rssi - 4, "LQUL": lq, "SNR": max(-10, min(12, 12 + (rssi + 60) / 4)),
            "TXPWR": 100, "LQDL": 100 if lq == 100 else lq - 3,
            "Um": Um, "Uc": Uc, "Im": Im, "Ic": Ic,
            "flx1": 0.4545 + da / 120, "flx2": 0.4545 - da / 120, "flx3": 0.4545 + de / 120, "flx4": 0.4545 + dr / 120,
        }
        chs = [1500 + da / 20 * 500, 1500 + de / 20 * 500, 1000 + thr * 1000, 1500 + dr / 20 * 500, 1900, 1500, 1500, 1000]
        for i in range(16):
            s[f"ch{i+1}"] = chs[i] if i < len(chs) else 1500
        s["_t"] = t
        s["_phase"] = phase
        s["_d"] = d
        s["_rho"] = rho
        out.append(s)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--taxa-voo", type=int, default=200, help="taxa do registro da placa de voo (o real é 2000)")
    ap.add_argument("--duracao", type=float, default=120.0)
    ap.add_argument("--saida", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "samples"))
    a = ap.parse_args()
    os.makedirs(a.saida, exist_ok=True)
    rnd = random.Random(3)

    # ---- placa de voo
    fl = simulate(a.taxa_voo, a.duracao)
    p_ref = fl[0]["P"]
    path = os.path.join(a.saida, "demo_voo_FLT_0001.BIN")
    with open(path, "wb") as f:
        f.write(h.flight_log_header(a.taxa_voo, 1, HOME, p_ref))
        for s in fl:
            f.write(h.encode_packet(s))
    print(f"{path}: {len(fl)} pacotes a {a.taxa_voo} Hz")

    # ---- estação de solo (100 pkt/s recebidos, perdas e queda de enlace)
    gs = simulate(100, a.duracao)
    path = os.path.join(a.saida, "demo_solo_GND_0001.BIN")
    rx_ok = crc = lost = fwd = 0
    last_rx_ms = 0
    with open(path, "wb") as f:
        f.write(h.ground_log_header())
        for k, s in enumerate(gs):
            t = s["_t"]
            gs_ms = int(1000 + t * 1000)
            dropout = 70.0 <= t < 73.0
            if dropout or rnd.random() < 0.015:
                lost += 1
                if rnd.random() < 0.3 and not dropout:
                    crc += 1
            else:
                rx_ok += 1
                last_rx_ms = gs_ms
                rssi = -45 - 20 * math.log10(max(s["_d"], 5) / 5) + rnd.gauss(0, 1.0)
                snr = max(-8.0, min(10.0, 10 + (rssi + 75) / 3))
                meta = h.RXMETA_STRUCT.pack(int(rssi * 10), int(snr * 10), gs_ms)
                f.write(h.encode_frame(h.FT_TELEMETRY, h.encode_packet(s) + meta))
                if k % 2 == 0:
                    fwd += 1
            if k % 100 == 50:   # 1 Hz: estados
                st = 3 if t < 8 else (4 if t < 12 else 5)
                fst = {"state": st, "flags": 0x07 if st == 5 else 0x06, "micros": s["micros"], "dev_present": 0x7FF,
                       "dev_fault": 0, "gnss_fix": 3, "gnss_numsv": 18, "gnss_hacc_cm": 90, "sd_file_index": 1,
                       "sd_ring_pct": 1, "op_mode": 5 if st == 5 else 4,
                       "sd_records": int(max(0, t - 12) * 2000), "sd_dropped": 0, "imu_exec_us_max": 112,
                       "imu_exec_us_avg": 74, "tx_skipped": int(t // 30), "fw_build": 1,
                       "home_lat_e7": int(HOME[0] * 1e7), "home_lon_e7": int(HOME[1] * 1e7),
                       "home_hmsl_mm": int(HOME[2] * 1000)}
                if not dropout:
                    meta = h.RXMETA_STRUCT.pack(-600, 90, gs_ms)
                    f.write(h.encode_frame(h.FT_FLIGHT_STATUS, h.encode_status(fst) + meta))
                age = gs_ms - last_rx_ms
                gst = {"state": 5 if age > 2000 else 4, "flags": 0x07 | (0x08 if age < 2000 else 0), "op_mode": 4,
                       "uptime_ms": gs_ms, "rx_ok": rx_ok, "rx_crc_err": crc, "rx_lost_est": lost,
                       "usb_forwarded": fwd, "sd_bytes": 512 + rx_ok * 142, "sd_file_index": 1,
                       "last_rx_age_ms": min(age, 65535), "last_rssi_x10": -600, "last_snr_x10": 90}
                f.write(h.encode_frame(h.FT_GS_STATUS, h.encode_gs_status(gst)))
    print(f"{path}: {rx_ok} pacotes recebidos, {lost} perdidos")

    # ---- formato legado do simulador (50 Hz, graus, zdot positivo para cima)
    path = os.path.join(a.saida, "demo_simulador.csv")
    sim = simulate(50, a.duracao)
    psi_acc, prev = 0.0, None
    with open(path, "w") as f:
        f.write("t,phi,theta,psi,Vinf,h,zdot,psidot,xddot,yddot\n")
        for s in sim:
            psi_acc = s["psi"] if prev is None else psi_acc + wrap(s["psi"] - prev)
            prev = s["psi"]
            f.write(f"{s['_t']:.3f},{s['phi']/D2R:.3f},{s['theta']/D2R:.3f},{psi_acc/D2R:.3f},{s['Vinf']:.3f},"
                    f"{s['h']:.3f},{-s['zdot']:.3f},{s['psidot']/D2R:.3f},{s['xddot']:.4f},{s['yddot']:.4f}\n")
    print(f"{path}: {len(sim)} linhas")


if __name__ == "__main__":
    main()
