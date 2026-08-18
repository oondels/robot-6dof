# Registro e Auditoria de Calibração das Juntas

Este documento mantém o histórico, medições brutas, decisões de projeto e parâmetros validados para cada junta do braço robótico de 6 graus de liberdade (6-DOF).

---

## Índice Geral das Juntas (1 a 6)

| Junta | Nome | Servo ID | Zero Mecânico | Direção | Faixa Angular | Tolerância | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | `base_yaw` | 1 | `2065 counts` | `+1` | `[-105.0°, 100.0°]` | `1.0°` | **Calibrada** |
| 2 | `shoulder_pitch` | 2 | `2050 counts` | `+1` | `[-1.0°, 165.0°]` | `1.0°` | **Calibrada** |
| 3 | `elbow_pitch` | 3 | `2022 counts` | `-1` | `[-1.0°, 155.0°]` | `1.0°` | **Calibrada** |
| 4 | `wrist_pitch` | 4 | `2060 counts` | `-1` | `[-1.0°, 155.0°]` | `1.0°` | **Calibrada** |
| 5 | `wrist_roll` | 5 | `2164 counts` | `-1` | `[-160.0°, 160.0°]` | `1.0°` | **Calibrada** |
| 6 | `gripper` | 6 | `2041 counts` | `+1` | `[-1.0°, 110.0°]` | `1.0°` | **Calibrada** |

---

## Detalhamento por Junta

### Junta 1 — `base_yaw` (Base Giratória)
- **Servo ID:** `1`
- **Função:** Rotação da base no plano horizontal (Yaw).
- **Zero Mecânico:** `2065 counts` ($0.0^\circ$).
- **Sentido:** Sentido positivo aumenta counts $\rightarrow$ `direction = 1`.
- **Extremo Negativo Medido:** `810 counts` ($\approx -110{,}3^\circ$).
- **Extremo Positivo Medido:** `3240 counts` ($\approx +103{,}3^\circ$).
- **Faixa Segura Calibrada:** `[-105.0°, +100.0°]` (margens de proteção de $61\text{ counts}$ e $38\text{ counts}$ antes dos batentes).
- **Tolerância:** `1.0°` ($\approx 11\text{ counts}$).

---

### Junta 2 — `shoulder_pitch` (Ombro)
- **Servo ID:** `2`
- **Função:** Elevação e inclinação do braço principal (Pitch).
- **Zero Mecânico:** `2050 counts` ($0.0^\circ$).
- **Sentido:** Sentido positivo aumenta counts $\rightarrow$ `direction = 1`.
- **Extremo Negativo:** Posição zero com recuo de repouso $\rightarrow$ `min_angle = -1.0°`.
- **Extremo Positivo Medido:** `4050 counts` ($\approx +175{,}8^\circ$).
- **Faixa Segura Calibrada:** `[-1.0°, +165.0°]` ($\approx 3927\text{ counts}$, com margem de segurança de $123\text{ counts}$ antes de $4050$ e $168\text{ counts}$ antes da borda $4095$).
- **Tolerância:** `1.0°` ($\approx 11\text{ counts}$).

---

### Junta 3 — `elbow_pitch` (Cotovelo)
- **Servo ID:** `3`
- **Função:** Articulação do antebraço (Pitch).
- **Zero Mecânico:** `2022 counts` ($0.0^\circ$).
- **Sentido:** Sentido positivo diminui counts $\rightarrow$ `direction = -1`.
- **Extremo Negativo:** Posição zero com recuo de repouso $\rightarrow$ `min_angle = -1.0°`.
- **Extremo Positivo Medido:** `100 counts` ($\approx +168{,}9^\circ$).
- **Faixa Segura Calibrada:** `[-1.0°, +155.0°]` ($\approx 257\text{ counts}$, com margem de segurança de $157\text{ counts} \approx 13{,}8^\circ$ antes de $100$).
- **Tolerância:** `1.0°` ($\approx 11\text{ counts}$).

---

### Junta 4 — `wrist_pitch` (Inclinação do Pulso)
- **Servo ID:** `4`
- **Função:** Elevação e inclinação do efetuador final / garra.
- **Zero Mecânico:** `2060 counts` ($0.0^\circ$).
- **Sentido:** Sentido positivo diminui counts $\rightarrow$ `direction = -1`.
- **Extremo Negativo:** Posição zero com recuo de repouso $\rightarrow$ `min_angle = -1.0°`.
- **Extremo Positivo Medido:** `140 counts` ($\approx +168{,}8^\circ$).
- **Faixa Segura Calibrada:** `[-1.0°, +155.0°]` ($\approx 297\text{ counts}$, com margem de segurança de $157\text{ counts} \approx 13{,}8^\circ$ antes de $140$).
- **Tolerância:** `1.0°` ($\approx 11\text{ counts}$).

---

### Junta 5 — `wrist_roll` (Rotação do Pulso)
- **Servo ID:** `5`
- **Função:** Rotação axial da garra.
- **Zero Mecânico:** `2164 counts` ($0.0^\circ$).
- **Sentido:** Sentido positivo diminui counts $\rightarrow$ `direction = -1`.
- **Extremo Negativo Medido:** `4095 counts`.
- **Extremo Positivo Medido:** `274 counts`.
- **Faixa Segura Calibrada:** `[-160.0°, +160.0°]` ($320^\circ$ de rotação linear e contínua).
- **Tolerância:** `1.0°` ($\approx 11\text{ counts}$).

---

### Junta 6 — `gripper` (Garra)
- **Servo ID:** `6`
- **Função:** Abertura e fechamento dos dedos da garra.
- **Zero Mecânico:** `2041 counts` ($0.0^\circ$, fechada).
- **Sentido:** Sentido de abertura aumenta counts $\rightarrow$ `direction = 1`.
- **Batente Máximo Medido:** $\approx 3545\text{ counts}$.
- **Faixa Segura Calibrada:** `[-1.0°, +110.0°]` ($\approx 3293\text{ counts}$, com $>20^\circ$ de recuo antes do batente).
- **Tolerância:** `1.0°` ($\approx 11\text{ counts}$).

---

## Histórico de Auditoria

| Data | Responsável | Ação | Racional |
| :--- | :--- | :--- | :--- |
| 18/08/2026 | Operador / Antigravity | Calibração da Junta 6 (`gripper`) | Zero em 2041 counts, faixa `[-1.0°, 110.0°]`. Validado no hardware. |
| 18/08/2026 | Operador / Antigravity | Centralização e Calibração da Junta 5 (`wrist_roll`) | Centralização do horn em 2164 counts para evitar salto 0/4095. Faixa `[-160.0°, 160.0°]`. Validado no hardware. |
| 18/08/2026 | Operador / Antigravity | Calibração das Juntas 4, 3, 2 e 1 | Medição física de zero, direção e limites seguros com margens de recuo mecânico. Todas as 6 juntas registradas com tolerância padrão de 1.0°. |
