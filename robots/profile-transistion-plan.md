# Plano de Alimentação do Perfil do Robô: `robots/arm-test1`

Este documento detalha o mapeamento e a alimentação dos arquivos de perfil do braço robótico em `robots/arm-test1` a partir dos dados validados e executáveis atualmente distribuídos no projeto (`robot_config.py`, `docs/CALIBRATION_LOG.md`, `src/application/`, `src/actions/`).

---

## 1. Descrição do Objetivo

O diretório `robots/arm-test1` foi preparado para servir como o **modelo de perfil declarativo** do braço robótico de 6 graus de liberdade (6-DOF).

Nossa missão é:
1. Analisar a organização de pastas e arquivos da pasta `robots/arm-test1/`.
2. Mapear e transferir com fidelidade todos os dados físicos, cinemáticos 1D, de hardware, limites, controle, calibração, segurança e poses atualmente salvos no código.
3. Para dados que **ainda não existem no projeto** (ex: parâmetros DH de cinemática direta/inversa, dimensões CAD dos elos, matrizes de transformação de *frames* cartesianos, ferramentas externas), manter a estrutura limpa e declarada, porém **sem preencher** (deixando campos nulos/comentados como pendentes).

---

## 2. Estrutura Identificada em `robots/arm-test1`

```text
robots/arm-test1/
├── README.md                 # Documentação e identificação do modelo
├── profile.yml               # Manifesto raiz do perfil (metadados e índices)
├── config/
│   ├── hardware.yml          # Barramento, portas, protocolo e servos
│   ├── calibration.yml       # Posições zero, direções e dados de calibração
│   ├── limits.yml            # Limites angulares, counts e limites do SDK
│   ├── control.yml           # Ganhos, velocidades padrão, tolerâncias e timeouts
│   ├── safety.yml            # Parada de emergência, clamp, anti-jump e stall
│   ├── kinematics.yml        # (Pendente) DH parameters, elos e workspace
│   └── frames.yml            # (Pendente) Frames base, TCP, world e câmera
├── poses/
│   └── presets.yml           # Poses nomeadas conhecidas (home, wave_small, etc.)
├── actions/
│   ├── preset/               # Ações pré-programadas
│   └── recorded/             # Metadados de ações gravadas
├── trajectories/             # Trajetórias gravadas de referência
├── tools/                    # Ferramentas acopladas (garra padrão)
└── audit/
    └── calibration_history.yml # Histórico de calibração e auditoria
```

---

## 3. Mapeamento dos Dados Existentes vs Pendentes

| Arquivo | Origem dos Dados Atuais | Status do Preenchimento |
| :--- | :--- | :--- |
| **`profile.yml`** | Metadados do projeto (`robot-6dof`, 6 eixos, Feetech) | **Preenchimento completo** |
| **`README.md`** | Síntese de `README.md`, `CALIBRATION_LOG.md` e specs | **Preenchimento completo** |
| **`config/hardware.yml`** | `src/infrastructure/scservo_bus.py`, `robot_config.py` | **Preenchimento completo** |
| **`config/calibration.yml`**| `robot_config.py`, `docs/CALIBRATION_LOG.md` | **Preenchimento completo** |
| **`config/limits.yml`** | `src/application/joint_config.py`, `robot_config.py` | **Preenchimento completo** |
| **`config/control.yml`** | `robot_config.py`, `keyboard_control.py`, `robot_arm.py` | **Preenchimento completo** |
| **`config/safety.yml`** | `Joint.enable_torque`, `move()`, `keyboard_control.py` | **Preenchimento completo** |
| **`config/kinematics.yml`**| Parâmetros DH / Comprimento de Elos / Inércia | **Sem preencher** *(Estrutura com placeholders vazios)* |
| **`config/frames.yml`** | Matrizes de Transformação Homogênea / TCP | **Sem preencher** *(Estrutura com placeholders vazios)* |
| **`poses/presets.yml`** | `src/calibration/test_arm_poses.py`, `home_pose.py` | **Preenchimento completo** (`home`, `wave_small`) |
| **`audit/calibration_history.yml`** | `docs/CALIBRATION_LOG.md` | **Preenchimento completo** |

---

## 4. Proposta Detalhada de Conteúdo por Arquivo

### 4.1. `robots/arm-test1/profile.yml`
```yaml
profile_version: "1.0.0"
robot:
  name: "arm-test1"
  type: "articulated_arm"
  dof: 6
  description: "Braço robótico de 6 graus de liberdade com servomotores inteligentes Feetech STS/SCS."
  created_at: "2026-08-18"
  updated_at: "2026-08-26"

configs:
  hardware: "config/hardware.yml"
  calibration: "config/calibration.yml"
  limits: "config/limits.yml"
  control: "config/control.yml"
  safety: "config/safety.yml"
  kinematics: "config/kinematics.yml"
  frames: "config/frames.yml"

poses: "poses/presets.yml"
audit: "audit/calibration_history.yml"
```

---

### 4.2. `robots/arm-test1/config/hardware.yml`
```yaml
bus:
  protocol: "feetech_scs_sts"
  driver: "scservo_sdk.sms_sts"
  default_port: "/dev/ttyUSB0"
  default_baudrate: 1000000
  communication_timeout_ms: 100

encoder:
  type: "magnetic_absolute"
  resolution_bits: 12
  steps_per_revolution: 4096
  raw_range: [0, 4095]

servos:
  broadcast_id: 254
  id_range: [0, 253]
  joints:
    - name: "base_yaw"
      id: 1
      model: "STS3215"
    - name: "shoulder_pitch"
      id: 2
      model: "STS3215"
    - name: "elbow_pitch"
      id: 3
      model: "STS3215"
    - name: "wrist_pitch"
      id: 4
      model: "STS3215"
    - name: "wrist_roll"
      id: 5
      model: "STS3215"
    - name: "gripper"
      id: 6
      model: "STS3215"
```

---

### 4.3. `robots/arm-test1/config/calibration.yml`
```yaml
joints:
  base_yaw:
    servo_id: 1
    zero_position_counts: 2065
    direction: 1
    calibrated_at: "2026-08-18"
    raw_measured_extremes:
      negative_counts: 810
      positive_counts: 3240

  shoulder_pitch:
    servo_id: 2
    zero_position_counts: 2050
    direction: 1
    calibrated_at: "2026-08-18"
    raw_measured_extremes:
      negative_counts: null
      positive_counts: 4050

  elbow_pitch:
    servo_id: 3
    zero_position_counts: 2033
    direction: -1
    calibrated_at: "2026-08-18"
    raw_measured_extremes:
      negative_counts: null
      positive_counts: 100

  wrist_pitch:
    servo_id: 4
    zero_position_counts: 2060
    direction: -1
    calibrated_at: "2026-08-18"
    raw_measured_extremes:
      negative_counts: null
      positive_counts: 140

  wrist_roll:
    servo_id: 5
    zero_position_counts: 2164
    direction: -1
    calibrated_at: "2026-08-18"
    raw_measured_extremes:
      negative_counts: 4095
      positive_counts: 274

  gripper:
    servo_id: 6
    zero_position_counts: 2041
    direction: 1
    calibrated_at: "2026-08-18"
    raw_measured_extremes:
      negative_counts: null
      positive_counts: 3545
```

---

### 4.4. `robots/arm-test1/config/limits.yml`
```yaml
sdk_limits:
  speed_range: [0, 3400]
  acceleration_range: [0, 254]
  encoder_range: [0, 4095]

joint_limits:
  base_yaw:
    min_angle_deg: -105.0
    max_angle_deg: 100.0
    zero_in_range_enforced: true

  shoulder_pitch:
    min_angle_deg: -1.0
    max_angle_deg: 165.0
    zero_in_range_enforced: true

  elbow_pitch:
    min_angle_deg: -1.0
    max_angle_deg: 155.0
    zero_in_range_enforced: true

  wrist_pitch:
    min_angle_deg: -1.0
    max_angle_deg: 155.0
    zero_in_range_enforced: true

  wrist_roll:
    min_angle_deg: -160.0
    max_angle_deg: 160.0
    zero_in_range_enforced: true

  gripper:
    min_angle_deg: -1.0
    max_angle_deg: 110.0
    zero_in_range_enforced: true
```

---

### 4.5. `robots/arm-test1/config/control.yml`
```yaml
defaults:
  speed: 400
  acceleration: 30
  sync_method: "SyncWrite"
  poll_interval_s: 0.05
  default_move_timeout_s: 5.0
  default_pose_timeout_s: 8.0

joint_tolerances:
  base_yaw:
    tolerance_deg: 1.3
    tolerance_counts: 15
  shoulder_pitch:
    tolerance_deg: 1.8
    tolerance_counts: 20
  elbow_pitch:
    tolerance_deg: 5.0
    tolerance_counts: 57
  wrist_pitch:
    tolerance_deg: 1.8
    tolerance_counts: 20
  wrist_roll:
    tolerance_deg: 1.8
    tolerance_counts: 20
  gripper:
    tolerance_deg: 2.0
    tolerance_counts: 23

teleoperation:
  jog_speed_deg_s: 30.0
  control_loop_dt_s: 0.04
```

---

### 4.6. `robots/arm-test1/config/safety.yml`
```yaml
emergency_stop:
  software_keys: ["esc"]
  action: "disable_torque_immediate"

torque_management:
  anti_jump_enabled: true
  description: "Lê a posição atual do encoder e envia comando de retenção antes de ligar o torque."

movement_monitoring:
  stall_detection:
    enabled: true
    rule: "Lança RuntimeError se servo parar (moving == False) fora da janela de tolerância."
  timeout_detection:
    enabled: true
    rule: "Lança TimeoutError se exceder o tempo limite sem convergir para o alvo."
  clamping:
    enabled: true
    rule: "Limita o ângulo desejado estritamente ao intervalo [min_angle, max_angle] da junta."
```

---

### 4.7. `robots/arm-test1/config/kinematics.yml` *(Não preenchido / Estrutura base)*
```yaml
# Modelo Cinemático do Braço (Pendente de medição física/CAD)
# O que não possui dados validados ainda foi mantido nulo.

convention: "standard_dh" # ou modified_dh

links:
  base_to_joint1:
    length_m: null
    mass_kg: null
  joint1_to_joint2:
    length_m: null
    mass_kg: null
  joint2_to_joint3:
    length_m: null
    mass_kg: null
  joint3_to_joint4:
    length_m: null
    mass_kg: null
  joint4_to_joint5:
    length_m: null
    mass_kg: null
  joint5_to_gripper:
    length_m: null
    mass_kg: null

dh_parameters:
  # junta: [a (m), alpha (rad), d (m), theta_offset (rad)]
  base_yaw: null
  shoulder_pitch: null
  elbow_pitch: null
  wrist_pitch: null
  wrist_roll: null
  gripper: null

workspace_limits:
  x_range_m: null
  y_range_m: null
  z_range_m: null
  max_reach_m: null
```

---

### 4.8. `robots/arm-test1/config/frames.yml` *(Não preenchido / Estrutura base)*
```yaml
# Transformações de Coordenadas e Frames de Referência (Pendente)
# Define a relação entre World, Base, TCP e Câmeras.

world_frame:
  origin: [0.0, 0.0, 0.0]
  orientation_rpy: [0.0, 0.0, 0.0]

base_frame:
  parent: "world_frame"
  translation_m: [0.0, 0.0, 0.0]
  rotation_rpy: [0.0, 0.0, 0.0]

tool_center_point_frame:
  parent: "wrist_roll"
  translation_m: null
  rotation_rpy: null

camera_frame:
  parent: null
  translation_m: null
  rotation_rpy: null
```

---

### 4.9. `robots/arm-test1/poses/presets.yml`
```yaml
presets:
  home:
    description: "Pose de repouso padrão com todos os ângulos em 0°."
    angles:
      base_yaw: 0.0
      shoulder_pitch: 0.0
      elbow_pitch: 0.0
      wrist_pitch: 0.0
      wrist_roll: 0.0
      gripper: 0.0

  wave_small:
    description: "Pose de demonstração suave de saudação."
    angles:
      base_yaw: 15.0
      shoulder_pitch: 20.0
      elbow_pitch: 20.0
      wrist_pitch: 10.0
      wrist_roll: 20.0
      gripper: 30.0
```

---

### 4.10. `robots/arm-test1/audit/calibration_history.yml`
```yaml
history:
  - date: "2026-08-18"
    author: "Operador / Antigravity"
    joint: "gripper"
    action: "Calibração física da Junta 6"
    details: "Zero em 2041 counts, faixa [-1.0°, 110.0°]. Validado no hardware."

  - date: "2026-08-18"
    author: "Operador / Antigravity"
    joint: "wrist_roll"
    action: "Centralização e Calibração da Junta 5"
    details: "Centralização do horn em 2164 counts para evitar rollover 0/4095. Faixa [-160.0°, 160.0°]."

  - date: "2026-08-18"
    author: "Operador / Antigravity"
    joint: "all"
    action: "Calibração das Juntas 4, 3, 2 e 1"
    details: "Medição de zero, direção e limites seguros com margens de recuo mecânico antes dos batentes."
```

---

## 5. Plano de Verificação

### Verificação Automatizada
- Executar a suíte de testes unitários do projeto para garantir que nenhuma alteração acidental foi realizada no código-fonte Python:
  ```bash
  python3 -m unittest discover -s tests -p "test_*.py"
  ```
- Validar a sintaxe dos arquivos YAML criados utilizando `yaml.safe_load` em Python para garantir conformidade estrutural.

### Verificação Manual
- Inspecionar cada arquivo gerado em `robots/arm-test1/` para confirmar que os dados correspondem exatamente a `robot_config.py` e `CALIBRATION_LOG.md`, e que os módulos pendentes (`kinematics.yml`, `frames.yml`) estão explicitamente sinalizados como `null` ou comentados.
