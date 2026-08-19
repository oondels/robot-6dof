# Guia Completo de Arquitetura, Engenharia e Código — Braço Robótico 6-DOF

Este documento fornece a explicação integral, exaustiva e estruturada da arquitetura de software, engenharia de controle, modelo de classes, matemática de conversão, calibração de hardware e testes do projeto **Robotics (6-DOF)**.

---

## 1. Visão Geral e Propósito do Projeto

O projeto é um framework de controle robótico em Python desenvolvido para operar de forma modular, segura e determinística um **braço robótico articulado de 6 graus de liberdade (6-DOF)** construído com servomotores inteligentes seriais com protocolo SMS-STS / SCServo (Feetech / Waveshare) via barramento serial RS485 / TTL a **1.000.000 baud** (`/dev/ttyUSB0`).

### Objetivos Centrais de Engenharia
1. **Segurança Física Máxima:** Nenhuma operação de hardware ou habilitação de torque pode ser executada sem validação rigorosa de limites angulares, verificação de alvos prévios e consentimento explícito do operador.
2. **Separação Rígida de Responsabilidades (SRP):** Configuração física imutável (`JointConfig`), adaptação de hardware (`Joint`), agregação orquestrada (`RobotArm`) e ponto de entrada (`main.py`).
3. **Isolamento e Testabilidade Total:** 100% da lógica de negócio, conversão matemática, timeouts e controle sincronizado de poses é validada através de simulação (`FakeServo`) sem abrir a porta serial real nem depender do hardware físico conectado.
4. **Movimentação Sincronizada Atômica:** Uso da tecnologia `SyncWrite` em barramento compartilhado *daisy-chain* para garantir que todas as juntas iniciem e executem suas trajetórias simultaneamente.

---

## 2. Princípios de Arquitetura e Engenharia de Software

### 2.1 Padrão em Camadas

```text
+-------------------------------------------------------------------+
|                        Camada de Aplicação                        |
|       main.py  /  calibration/test_arm_poses.py  /  CLI scripts   |
+-------------------------------------------------------------------+
                                 │
                                 ▼
+-------------------------------------------------------------------+
|                      Camada de Orquestração                       |
|                   RobotArm (models/RobotArm.py)                   |
|        - Validação de poses completas (6 juntas)                  |
|        - Despacho em lote atômico via SyncWrite                   |
|        - Monitoramento conjunto e timeout de convergência         |
+-------------------------------------------------------------------+
                                 │
                                 ▼
+-------------------------------------------------------------------+
|                   Camada de Domínio / Unidade                     |
|                      Joint (models/Joint.py)                      |
|        - Telemetria de posição, ângulo e estado 'moving'          |
|        - Controle seguro de Torque (endereço 40)                  |
|        - Movimento individual monitorado (move/command)           |
+-------------------------------------------------------------------+
            │                                           │
            ▼                                           ▼
+-----------------------+                   +-----------------------+
|  Configuração Pura    |                   |  Validação & SDK      |
|  JointConfig          |                   |  utils/validation.py  |
|  (models/joint_config)|                   |  scservo_sdk          |
|  - Matemática pura    |                   |  (ou tests/fake_servo)|
|  - Imutabilidade      |                   +-----------------------+
+-----------------------+
```

### 2.2 Imutabilidade e Tipagem Estrita
- **Dataclasses com `frozen=True` e `slots=True`:** As classes de configuração (`JointConfig`) e de telemetria (`MovementStatus`) são estritamente imutáveis após a construção. `slots=True` otimiza o uso de memória e impede a criação de atributos arbitrários em tempo de execução.
- **Validações Pré-Construção (`__post_init__`):** O objeto nunca assume um estado inválido. Qualquer parâmetro inconsistente (ex.: velocidade negativa, limite mínimo maior que o máximo, ID inválido) lança exceções imediatas antes que o objeto seja utilizado.

### 2.3 Duck Typing e Test Doubles
A classe `Joint` e a classe `RobotArm` não herdam diretamente do SDK proprietário, mas esperam uma interface que contenha métodos fundamentais (`ReadPosSpeed`, `ReadMoving`, `WritePosEx`, `write1ByteTxRx`, `read1ByteTxRx`, `groupSyncWrite`). Isso permite que os testes unitários injetem um mock de alta fidelidade (`FakeServo`) com total determinismo e sem efeitos colaterais.

### 2.4 Habilitação Defensiva de Torque
Em servomotores digitais industriais, se o registrador de torque for habilitado enquanto o alvo interno estiver em uma posição diferente da atual, o servo aplicará força máxima instantânea para alcançar o alvo antigo, causando tranco mecânico violento ou colisão.
O projeto implementa uma regra de proteção mandatória no método `Joint.enable_torque()`:
1. Lê a posição física atual do encoder (`ReadPosSpeed`).
2. Escreve a posição atual como alvo (`WritePosEx`).
3. Somente então escreve `1` no registrador `ADDR_TORQUE_ENABLE (40)`.
4. Relê o registrador para confirmar que o torque foi ativado com sucesso.

---

## 3. Mapa de Arquivos e Estrutura do Repositório

```text
robotics/
│
├── main.py                             # Ponto de entrada padrão (Composition Root)
├── robot_config.py                     # Fonte da verdade das 6 juntas calibradas
├── requirements.txt                    # Dependências do projeto
│
├── models/                             # Camada de domínio e modelos
│   ├── __init__.py
│   ├── joint_config.py                 # JointConfig (metadados e conversão matemática)
│   ├── Joint.py                        # Joint (operações no hardware) e MovementStatus
│   └── RobotArm.py                     # RobotArm (coordenação e SyncWrite de 6 juntas)
│
├── calibration/                        # Ferramentas de calibração e teste em bancada
│   ├── __init__.py
│   ├── read_joint_position.py          # Leitor passivo de counts sob demanda (Enter)
│   ├── read_joint_position_continuous.py # Leitor contínuo com detecção de movimento
│   ├── test_joint_motion.py            # Testador interativo de movimento para junta única
│   └── test_arm_poses.py               # Testador interativo de poses sincronizadas (SyncWrite)
│
├── utils/                              # Utilitários transversais
│   ├── __init__.py
│   └── validation.py                   # Validação de códigos de status/erro do SDK
│
├── tests/                              # Suíte completa de testes automatizados (82 testes)
│   ├── __init__.py
│   ├── fake_servo.py                   # Simulador de hardware e memória de registradores
│   ├── test_joint_config.py            # Testes de limites, erros e conversão de ângulos
│   ├── test_joint.py                   # Testes de torque, telemetria e loops de movimento
│   ├── test_robot_arm.py               # Testes de RobotArm, SyncWrite e poses simultâneas
│   ├── test_fake_servo.py              # Testes do próprio simulador de hardware
│   ├── test_read_joint_position.py     # Testes da ferramenta de leitura
│   ├── test_test_joint_motion.py       # Testes da CLI de teste de junta única
│   └── test_test_arm_poses.py          # Testes da CLI de teste de poses completas
│
└── docs/                               # Manuais técnicos e registros de calibração
    ├── GUIA_COMPLETO_DO_PROJETO.md     # Este manual detalhado
    ├── ARCHITECTURE.md                 # Arquitetura e fluxos operacionais
    ├── MODULES.md                      # Referência detalhada de módulos e APIs
    ├── CALIBRATION_LOG.md              # Auditoria e histórico de medições físicas
    ├── CALIBRATION.md                  # Procedimentos práticos de calibração
    ├── COMMANDS_AND_TESTING_GUIDE.md   # Guia de comandos e execução de testes
    └── SAFETY_AND_TESTING.md           # Regras de segurança operacional
```

---

## 4. Detalhamento Técnico das Classes e Módulos

### 4.1 `models/joint_config.py` — `JointConfig`

Representa a configuração física e geométrica imutável de uma junta. Não possui nenhum conhecimento de barramento serial ou hardware.

#### Atributos
- `name: str`: Identificador humano (ex.: `"base_yaw"`, `"shoulder_pitch"`).
- `servo_id: int`: Identificador único no barramento serial (`0` a `253`). O ID `254` é reservado pelo protocolo para Broadcast.
- `zero_position: int`: Posição bruta do encoder (em counts de `0` a `4095`) correspondente ao ângulo físico de `0.0°`.
- `direction: int`: Polaridade de movimento (`1` para sentido direto, `-1` para sentido invertido).
- `min_angle: float`: Ângulo físico mínimo permitido em graus.
- `max_angle: float`: Ângulo físico máximo permitido em graus.
- `speed: int = 1000`: Velocidade padrão de deslocamento (`0` a `3400` counts/s).
- `acc: int = 100`: Taxa de aceleração/desaceleração (`0` a `254`).
- `tolerance_deg: float = 1.0`: Margem de tolerância aceitável para considerar o alvo alcançado.

#### Métodos e Propriedades
- `tolerance_counts -> int`: Converte a tolerância angular para resolução discreta em counts:
  $$\text{tolerance\_counts} = \max\left(1, \operatorname{round}\left(\text{tolerance\_deg} \times \frac{4096}{360.0}\right)\right)$$
- `angle_to_position(angle: float) -> int`: Valida se o ângulo está dentro de `[min_angle, max_angle]` e calcula a posição do encoder em counts.
- `position_to_angle(position: int) -> float`: Valida se os counts estão dentro do intervalo seguro mapeado e calcula o ângulo físico correspondente em graus.

---

### 4.2 `models/Joint.py` — `MovementStatus` e `Joint`

#### `MovementStatus`
Dataclass imutável que captura uma fotografia pontual do estado de movimento:
- `target_position: int`: Posição pretendida em counts.
- `current_position: int`: Posição real lida no instante da consulta.
- `position_error: int`: Erro absoluto $| \text{target} - \text{current} |$.
- `moving: bool`: Flag de movimento informada pelo registrador do servo.
- `within_tolerance: bool`: Booleano que indica se $\text{position\_error} \le \text{tolerance\_counts}$.

#### `Joint`
Adaptador responsável pela comunicação e controle de um servo específico.

- **Leitura de Estado:**
  - `current_position() -> int`: Executa `ReadPosSpeed` e retorna os counts brutos.
  - `current_angle() -> float`: Lê a posição e converte para graus usando `config.position_to_angle`.
  - `is_moving() -> bool`: Executa `ReadMoving` no registrador do servo.
  - `movement_status(target_position: int) -> MovementStatus`: Gera uma fotografia consolidada do estado.
- **Gerenciamento de Torque:**
  - `enable_torque()`: Escreve a posição atual no alvo antes de habilitar o registrador 40.
  - `disable_torque()`: Escreve 0 no registrador 40 e confirma o desligamento.
  - `is_torque_enabled() -> bool`: Consulta o registrador 40 via `read1ByteTxRx`.
- **Movimentação:**
  - `command(angle, speed, acc) -> int`: Valida limites, envia `WritePosEx` e retorna o alvo em counts imediatamente (não bloqueante).
  - `move(angle, speed, acc, timeout, poll_interval) -> MovementStatus`: Envia o comando e executa um loop de espera até que a junta alcance a tolerância desejada. Lança `RuntimeError` caso o motor pare prematuramente fora da tolerância ou `TimeoutError` caso exceda o tempo estipulado.

---

### 4.3 `models/RobotArm.py` — `RobotArm`

Classe agregadora que orquestra o conjunto completo de juntas do robô.

#### Validações Invariantes
- Rejeita lista de juntas vazia.
- Impede cadastro de juntas com o mesmo nome (case-insensitive).
- Impede duplicidade de `servo_id`.

#### Funcionalidades Principais
- **Acesso:** Permite acesso por nome de forma indexada (`arm["gripper"]` ou `arm.joint("base_yaw")`).
- **Telemetria Global:**
  - `current_angles() -> dict[str, float]`: Dicionário com o ângulo atual de todas as juntas.
  - `current_positions() -> dict[str, int]`: Dicionário com as posições em counts.
- **Gerenciamento de Torque Coletivo:**
  - `enable_torque()` / `disable_torque()`: Habilita ou desabilita o torque de todas as juntas com proteção contra trancos.
  - `is_torque_enabled() -> bool`: Retorna `True` apenas se todas as juntas estiverem energizadas.
- **Validação de Poses:**
  - `validate_pose(pose: dict[str, float])`: Garante que a pose contém exatamente todas as juntas configuradas e que todos os ângulos respeitam os limites operacionais de cada articulação.
- **Movimentação Sincronizada com `SyncWrite`:**
  - `command_pose(pose: dict[str, float]) -> dict[str, int]`: Limpa a fila `groupSyncWrite`, empacota os dados de todas as juntas com `SyncWritePosEx` e despacha um único pacote broadcast na rede serial via `groupSyncWrite.txPacket()`.
  - `move_pose(pose, timeout, poll_interval) -> dict[str, MovementStatus]`: Dispara a pose sincronizada e monitora todas as juntas em paralelo até que todas alcancem a posição desejada dentro da tolerância, tratando falhas de parada precoce e timeouts coletivos.

---

### 4.4 `utils/validation.py` — `validate_result`

O SDK `scservo_sdk` comunica status através de dois parâmetros inteiros:
1. `result`: Código de sucesso ou erro de transporte físico/serial (ex.: `COMM_SUCCESS`, `COMM_TX_FAIL`, `COMM_RX_TIMEOUT`).
2. `error`: Código de status retornado no cabeçalho do pacote pelo microcontrolador do servo (ex.: sobreaquecimento, sobretensão, sobrecarga).

A função `validate_result(servo, result, error, operation)` intercepta esses códigos e lança exceções Python `RuntimeError` detalhadas e formatadas, evitando que erros silenciosos passem despercebidos.

---

## 5. Modelo Matemático e Cinemática de Conversão

O sistema utiliza servomotores de **12 bits de resolução**, o que divide uma revolução completa ($360^\circ$) em **4096 posições discretas** (counts de $0$ a $4095$).

### 5.1 Relação Angular por Passo
$$\Delta\theta = \frac{360^\circ}{4096} = 0{,}087890625^\circ \text{ por count}$$

### 5.2 Conversão de Graus para Counts (Encoder)
$$\text{position} = \operatorname{round}\left(\text{zero\_position} + \text{direction} \times \text{angle} \times \frac{4096}{360.0}\right)$$

Onde:
- $\text{zero\_position}$: Count medido fisicamente quando a junta está na sua posição geométrica neutra ($0.0^\circ$).
- $\text{direction}$: $+1$ se a rotação positiva aumenta os counts do encoder; $-1$ se diminui.
- $\text{angle}$: Ângulo desejado em graus ($^\circ$).

### 5.3 Conversão de Counts para Graus
$$\text{angle} = \frac{(\text{position} - \text{zero\_position}) \times 360.0}{\text{direction} \times 4096}$$

### 5.4 Erro de Quantização
Como os comandos enviados aos servomotores são números inteiros, a conversão $\text{graus} \rightarrow \text{counts} \rightarrow \text{graus}$ gera um erro residual de quantização de no máximo meio count ($\approx \pm 0{,}04395^\circ$).

---

## 6. Configuração Física e Calibração das 6 Juntas (`robot_config.py`)

Todas as 6 juntas foram calibradas e validadas no hardware real, com margens de recuo contra batentes mecânicos e proteção contra transição de ciclo:

| Junta | Nome | Servo ID | Zero Mecânico | Direção | Faixa Angular Segura | Velocidade | Aceleração | Tolerância |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **J1** | `base_yaw` | **1** | `2065 counts` | `+1` | `[-105.0°, +100.0°]` | 400 | 30 | 1.3° |
| **J2** | `shoulder_pitch` | **2** | `2050 counts` | `+1` | `[-1.0°, +165.0°]` | 400 | 30 | 1.8° |
| **J3** | `elbow_pitch` | **3** | `2022 counts` | `-1` | `[-1.0°, +155.0°]` | 400 | 30 | 2.3° |
| **J4** | `wrist_pitch` | **4** | `2060 counts` | `-1` | `[-1.0°, +155.0°]` | 400 | 30 | 1.8° |
| **J5** | `wrist_roll` | **5** | `2164 counts` | `-1` | `[-160.0°, +160.0°]` | 400 | 30 | 1.8° |
| **J6** | `gripper` | **6** | `2041 counts` | `+1` | `[-1.0°, +110.0°]` | 400 | 30 | 1.0° |

### Decisões de Engenharia na Calibração
- **Junta 5 (`wrist_roll`):** O horn do servo foi centralizado fisicamente em `2164 counts`. Isso garante que a faixa de $320^\circ$ ($[-160^\circ, +160^\circ]$) ocorra integralmente de $274$ a $4095$ counts, sem nunca cruzar a descontinuidade $4095 \leftrightarrow 0$ do encoder magnético.
- **Juntas 2, 3 e 4 (Cadeia de Elevação/Pitch):** Possuem limite inferior em `-1.0°` (com pequena margem de repouso estrutural) e limites superiores que preservam $>10^\circ$ de distância em relação aos limites mecânicos das dobradiças e cabos.
- **Junta 6 (`gripper`):** Zero mecânico em `2041 counts` (totalmente fechada), abrindo até `110.0°` sem forçar o mecanismo de engrenagens contra o batente final.

---

## 7. Protocolo de Comunicação Serial e SyncWrite

O barramento serial dos servos STS opera em topologia de meia-duplex em cascata (*daisy chain*).

### 7.1 Pacotes Individuais vs. `SyncWrite`
- Em comandos individuais (`Joint.command`), um pacote de instrução é enviado a cada servo sequencialmente. Isso causa um pequeno atraso temporal entre a primeira e a última junta.
- Com `RobotArm.command_pose()`, o sistema utiliza a instrução **`SyncWrite` (Broadcast)**. Os dados de destino de todos os 6 servos são agrupados em uma única mensagem serial. Quando o pacote chega na linha, todos os servos iniciam seus movimentos no mesmo microssegundo.

```text
Estrutura do Pacote SyncWrite:
[Cabeçalho 0xFF 0xFF] [ID Broadcast 0xFE] [Comprimento] [Instrução SyncWrite]
  ├── Registrador Inicial (Posição/Velocidade/Aceleração)
  ├── Tamanho dos Dados por Servo (6 bytes: Pos_L, Pos_H, Spd_L, Spd_H, Acc_L, Acc_H)
  ├── [ID 1] [Dados Junta 1]
  ├── [ID 2] [Dados Junta 2]
  ├── [ID 3] [Dados Junta 3]
  ├── [ID 4] [Dados Junta 4]
  ├── [ID 5] [Dados Junta 5]
  └── [ID 6] [Dados Junta 6]
  [Checksum]
```

---

## 8. Ferramental Interativo e Scripts de Operação

### 8.1 Leitura Passiva de Encoder (`calibration/read_joint_position.py`)
Permite inspecionar a posição de qualquer servo sem acionar torque e sem aplicar movimento:
```bash
python -m calibration.read_joint_position --servo-id 1
```

### 8.2 Leitura Contínua de Movimento (`calibration/read_joint_position_continuous.py`)
Monitora o encoder em tempo real exibindo a leitura apenas quando a junta for movimentada manualmente:
```bash
python -m calibration.read_joint_position_continuous --servo-id 5
```

### 8.3 Teste Unitário de Movimento (`calibration/test_joint_motion.py`)
Permite comandar com segurança uma junta individual informando ângulos em graus:
```bash
python -m calibration.test_joint_motion --joint gripper
```

### 8.4 Testador Integrado de Poses Sincronizadas (`calibration/test_arm_poses.py`)
Executa poses coordenadas em todo o braço robótico:
```bash
python -m calibration.test_arm_poses
```
Oferece menu interativo:
- `1`: Pose `home` (todos os ângulos em $0.0^\circ$).
- `2`: Pose `wave_small` (movimento coordenado suave de demonstração).
- `c`: Entrada manual de ângulos para cada junta com validação de limites.
- `q`: Sair e desligar torque de forma segura.

---

## 9. Engenharia de Testes e Simulação de Hardware (`tests/fake_servo.py`)

A robustez da base de código é sustentada por **82 testes automatizados** que executam em frações de segundo sem necessidade de hardware físico:

```bash
python -m unittest discover -s tests -v
```

### Arquitetura do `FakeServo`
O `FakeServo` replica o comportamento interno do microcontrolador dos servos:
- **Tabela de Registradores:** Mantém memória virtual de registradores de 1 e 2 bytes (ex.: registrador `40` para torque).
- **Fila de Estados de Posição (`position_sequence`):** Permite programar a evolução das leituras ao longo do tempo para testar convergência, paradas mecânicas e cenários de erro.
- **Fila de Estados de Movimento (`moving_sequence`):** Permite simular o servo em trânsito (`moving=1`) e sua chegada ao destino (`moving=0`).
- **Simulação de `groupSyncWrite`:** Registra e valida os pacotes agrupados de escrita síncrona.

---

## 10. Checklist de Segurança Operacional

Antes de ligar a fonte de alimentação ou executar scripts com torque:
1. **Fixação da Base:** Garanta que a base do braço esteja firmemente aparafusada ou presa à bancada de testes.
2. **Área Desobstruída:** Assegure um raio livre de pelo menos 60 cm ao redor do braço.
3. **Alívio de Carga na Energização:** Ao habilitar o torque pelo software, forneça leve suporte manual ao braço para amortecer qualquer ajuste inicial de carga gravitacional.
4. **Desativação de Emergência:** O operador deve manter acesso imediato à tecla `Ctrl+C` ou ao interruptor geral da fonte de alimentação de bancada (7.4V - 12V).
