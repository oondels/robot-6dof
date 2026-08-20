# Robotics — Braço Robótico 6-DOF

Framework modular e didático em Python para controle determinístico, seguro e em tempo real de um **braço robótico articulado de 6 graus de liberdade (6-DOF)**, utilizando servomotores inteligentes seriais com protocolo **SMS-STS / SCServo** (Feetech / Waveshare) via barramento serial RS485/TTL a **1.000.000 baud** (`/dev/ttyUSB0`).

O projeto prioriza **segurança física**, **separação estrita de responsabilidades**, **testabilidade sem hardware** via simulador (*test doubles*) e **movimentação atômica síncrona** com tecnologia `SyncWrite`.

---

## 📊 Estado Atual do Projeto

| Funcionalidade / Componente | Status | Detalhes |
| :--- | :---: | :--- |
| **Configuração Física das Juntas (`JointConfig`)** | ✅ Concluído | Imutável (`frozen`), validação estrita pré-construção, conversão exata $\text{graus} \leftrightarrow \text{counts}$ e cálculo de tolerância discreta. |
| **Calibração Real das 6 Juntas (`robot_config.py`)** | ✅ Concluído | Todas as 6 juntas (`base_yaw`, `shoulder_pitch`, `elbow_pitch`, `wrist_pitch`, `wrist_roll`, `gripper`) medidas e validadas no hardware com margens de recuo contra batentes mecânicos. |
| **Controle de Junta Individual (`Joint`)** | ✅ Concluído | Telemetria de posição/ângulo, controle seguro de torque (com gravação de alvo prévio contra trancos), comando assíncrono e `move()` com monitoramento de tolerância e timeout. |
| **Fotografia Imutável de Movimento (`MovementStatus`)** | ✅ Concluído | Diagnóstico com `target_position`, `current_position`, `position_error`, `moving` e `within_tolerance`. |
| **Controlador Coordenado (`RobotArm`)** | ✅ Concluído | Agregação imutável de 6 juntas, validação estrita de poses completas, telemetria coletiva e controle de torque unificado. |
| **Movimento Simultâneo Atômico (`SyncWrite`)** | ✅ Concluído | Despacho de pacote broadcast único via `SyncWritePosEx` para início simultâneo de todas as juntas com monitoramento conjunto de convergência. |
| **Roteamento de Ações e CLI (`actions/` e `main.py`)** | ✅ Concluído | CLI com suporte a flags (`--action`, `--port`, `--baudrate`), despachando para status, testador interativo de poses ou módulo mirror. |
| **Ferramentas de Calibração e Bancada (`calibration/`)** | ✅ Concluído | Leitor de counts sob demanda, leitor contínuo por movimento, testador de junta individual e testador de poses sincronizadas. |
| **Suíte de Testes Automatizados (`tests/`)** | ✅ Concluído | **103 testes unitários** passando com `unittest` e simulador de alta fidelidade (`FakeServo`), com 0% de dependência de hardware conectado. |
| **Cinemática Direta / Inversa e Trajetórias Cartesianas** | ⏳ Futuro | Planejado para versões posteriores após consolidação da camada de controle angular. |

---

## 🏗️ Arquitetura do Sistema

O projeto é estruturado em camadas desacopladas com fluxo unidirecional:

```text
               ┌─────────────────────────────────────────────────────────┐
               │                    Camada de Entrada                    │
               │        main.py  /  actions/router.py  /  CLIs           │
               └────────────────────────────┬────────────────────────────┘
                                            │
                                            ▼
               ┌─────────────────────────────────────────────────────────┐
               │                 Orquestração (RobotArm)                 │
               │   - Validação de poses completas (6 juntas)             │
               │   - Pacote atômico broadcast via SyncWrite              │
               │   - Monitoramento paralelo e timeout de convergência    │
               └────────────────────────────┬────────────────────────────┘
                                            │
                                            ▼
               ┌─────────────────────────────────────────────────────────┐
               │                 Domínio / Unidade (Joint)               │
               │   - Telemetria de posição, ângulo e flag moving         │
               │   - Controle seguro de Torque (endereço 40)             │
               │   - Movimento individual monitorado (move / command)    │
               └──────────────┬───────────────────────────┬──────────────┘
                              │                           │
                              ▼                           ▼
               ┌─────────────────────────────┐ ┌─────────────────────────┐
               │ Configuração (JointConfig)  │ │   SDK / Comunicação     │
               │ - zero_position, direção    │ │   - scservo_sdk         │
               │ - limites [min, max]        │ │   - FakeServo (testes)  │
               │ - tolerância, vel, acc      │ │   - validate_result()   │
               └─────────────────────────────┘ └─────────────────────────┘
```

### Juntas Calibradas em `robot_config.py`

| ID | Nome | Função Mecânica | Zero Mecânico | Sentido | Faixa Angular Segura | Velocidade | Aceleração | Tolerância |
| :-: | :--- | :--- | :-: | :-: | :-: | :-: | :-: | :-: |
| **1** | `base_yaw` | Rotação da base (Yaw) | 2065 counts | `+1` | `[-105.0°, +100.0°]` | 400 | 30 | 1.3° |
| **2** | `shoulder_pitch` | Elevação do ombro (Pitch) | 2050 counts | `+1` | `[-1.0°, +165.0°]` | 400 | 30 | 1.8° |
| **3** | `elbow_pitch` | Articulação do cotovelo | 2022 counts | `-1` | `[-1.0°, +155.0°]` | 400 | 30 | 2.3° |
| **4** | `wrist_pitch` | Inclinação do pulso | 2060 counts | `-1` | `[-1.0°, +155.0°]` | 400 | 30 | 1.8° |
| **5** | `wrist_roll` | Rotação axial da garra | 2164 counts | `-1` | `[-160.0°, +160.0°]` | 400 | 30 | 1.8° |
| **6** | `gripper` | Abertura/fechamento da garra | 2041 counts | `+1` | `[-1.0°, +110.0°]` | 400 | 30 | 1.0° |

---

## 🚀 O Que Pode Ser Executado e Como Executar

### 1. Aplicação Principal (`main.py`)

Ponto de entrada central do robô com roteamento integrado de ações.

```bash
# Exibe o status angular e posição em counts de todas as 6 juntas (padrão)
python main.py

# Explicitando a ação de status
python main.py --action status

# Executa o testador interativo de poses sincronizadas via SyncWrite
python main.py --action test

# Executa a ação de espelhamento / gravação de movimentos
python main.py --action mirror

# Lista todas as ações gravadas disponíveis em recorded_actions/
python main.py --action list

# Executa diretamente uma ação gravada previamente (sempre alinha na Home antes)
python main.py --action pegar_copo

# Especificando porta serial e baudrate customizados
python main.py --action status --port /dev/ttyUSB0 --baudrate 1000000
```

#### Flags de Linha de Comando do `main.py`:
- `--action {status, test, mirror, list, <nome_da_acao>}`: Ação a ser executada (padrão: `status`).
  - `status`: Lê a telemetria atual de todas as juntas sem habilitar torque e exibe no terminal.
  - `test`: Inicia o menu interativo de poses síncronas (`home`, `wave_small`, customizada).
  - `mirror`: Roteia para o módulo de espelhamento e gravação de poses (Teach & Repeat), com gravação manual, persistência em JSON, opção de salvar como ação nomeada e seleção entre Modo 1 (Original) e Modo 2 (Suavizado).
  - `list`: Lista em tabela todas as ações salvas no diretório `recorded_actions/`.
  - `<nome_da_acao>`: Carrega e executa a ação suavizada correspondente em `recorded_actions/`, posicionando o robô na pose Home antes da execução.
- `--port PORT`: Caminho do dispositivo serial (padrão: `/dev/ttyUSB0`).
- `--baudrate BAUDRATE`: Taxa de transmissão em baud (padrão: `1000000`).

---

### 2. Ferramentas de Calibração e Teste de Bancada (`calibration/`)

#### A. Leitor de Posição Sob Demanda (Passivo, Sem Torque)
Lê os counts do encoder a cada pressão da tecla `Enter`. Não aciona motores e não altera torque.
```bash
python -m calibration.read_joint_position --servo-id 1 --port /dev/ttyUSB0 --baudrate 1000000
```
- Flags: `--servo-id` (ID do servo, padrão: `6`), `--port`, `--baudrate`.

#### B. Leitor de Posição Contínuo (Passivo, Sem Torque)
Monitora o encoder em tempo real e exibe atualizações automáticas conforme a junta é movida manualmente.
```bash
python -m calibration.read_joint_position_continuous --servo-id 5 --port /dev/ttyUSB0 --baudrate 1000000
```
- Flags: `--servo-id` (ID do servo, padrão: `6`), `--port`, `--baudrate`.

#### C. Teste de Movimento de Junta Única (Supervisionado, Com Torque)
Comanda uma junta individual por ângulo em graus, com confirmação obrigatória de torque e limites validados.
```bash
python -m calibration.test_joint_motion --joint gripper --port /dev/ttyUSB0 --baudrate 1000000
```
- Flags: `--joint` (nome ou ID da junta, padrão: `gripper`), `--port`, `--baudrate`.

#### D. Testador de Poses Sincronizadas do Braço Completo (`SyncWrite`)
Menu interativo para disparo de poses pré-programadas ou manuais em todas as 6 juntas simultaneamente.
```bash
python -m calibration.test_arm_poses --port /dev/ttyUSB0 --baudrate 1000000
```
- Flags: `--port`, `--baudrate`.

---

### 3. Execução da Suíte de Testes Automatizados (Sem Hardware)

A suíte completa roda em memória usando `FakeServo`, sem tocar na porta serial:

```bash
# Executa todos os 89 testes unitários
python -m unittest discover -s tests -v

# Executar suítes específicas
python -m unittest tests.test_robot_arm -v       # Testes de RobotArm e SyncWrite
python -m unittest tests.test_joint -v           # Testes de Joint, torque e movimento
python -m unittest tests.test_joint_config -v    # Testes de JointConfig e matemática
python -m unittest tests.test_actions -v         # Testes do roteador de ações do main.py
python -m unittest tests.test_fake_servo -v      # Testes do simulador de hardware
python -m unittest tests.test_test_arm_poses -v  # Testes da CLI de poses sincronizadas
```

---

## 📁 Estrutura do Repositório

```text
robotics/
├── main.py                             # Ponto de entrada padrão (CLI e Composition Root)
├── robot_config.py                     # Fonte da verdade: 6 juntas calibradas e validadas
├── requirements.txt                    # Dependências do projeto
│
├── actions/                            # Camada de ações e roteamento da CLI
│   ├── __init__.py
│   ├── router.py                       # Roteador de ações (status, test, mirror)
│   └── mirror_action.py                # Ação de espelhamento e gravação de movimentos
│
├── models/                             # Camada de domínio e modelos matemáticos
│   ├── __init__.py
│   ├── joint_config.py                 # JointConfig (metadados imutáveis e conversão)
│   ├── Joint.py                        # Joint (operações no hardware) e MovementStatus
│   └── RobotArm.py                     # RobotArm (coordenação e SyncWrite de 6 juntas)
│
├── calibration/                        # Ferramentas interativas de calibração e bancada
│   ├── __init__.py
│   ├── read_joint_position.py          # Leitor passivo sob demanda (Enter)
│   ├── read_joint_position_continuous.py # Leitor contínuo com detecção de movimento
│   ├── test_joint_motion.py            # Teste supervisionado de junta individual
│   └── test_arm_poses.py               # Teste interativo de poses completas (SyncWrite)
│
├── utils/                              # Utilitários de comunicação e validação
│   ├── __init__.py
│   └── validation.py                   # Validação rigorosa dos códigos de erro do SDK
│
├── tests/                              # Suíte completa de 89 testes automatizados
│   ├── __init__.py
│   ├── fake_servo.py                   # Simulador de hardware e memória de registradores
│   ├── test_actions.py                 # Testes do roteador de ações e flags da CLI
│   ├── test_joint_config.py            # Testes de limites e conversões de coordenadas
│   ├── test_joint.py                   # Testes de torque, telemetria e loops de espera
│   ├── test_robot_arm.py               # Testes de RobotArm, SyncWrite e poses conjuntas
│   ├── test_fake_servo.py              # Testes unitários do próprio simulador
│   ├── test_read_joint_position.py     # Testes do leitor passivo de calibração
│   ├── test_test_joint_motion.py       # Testes da CLI de teste de junta única
│   └── test_test_arm_poses.py          # Testes da CLI de poses sincronizadas
│
├── docs/                               # Documentação aprofundada de engenharia
│   ├── GUIA_COMPLETO_DO_PROJETO.md     # Manual completo de arquitetura, matemática e código
│   ├── ARCHITECTURE.md                 # Princípios arquiteturais, camadas e fluxos
│   ├── MODULES.md                      # Referência detalhada de módulos e APIs públicas
│   ├── CALIBRATION_LOG.md              # Auditoria histórica das medições físicas
│   ├── COMMANDS_AND_TESTING_GUIDE.md   # Guia detalhado de comandos e testes
│   ├── SAFETY_AND_TESTING.md           # Normas de segurança e integridade física
│   └── CALIBRATION.md                  # Protocolo de calibração manual de juntas
│
├── PLAN.md                             # Planejamento pedagógico e arquitetura futura
└── TASKS.md                            # Checklist de desenvolvimento e marcos
```

---

## 📚 Índice de Documentação Aprofundada

Para detalhes técnicos avançados, consulte os guias dedicados em `docs/`:

- 📘 [**Guia Completo do Projeto**](docs/GUIA_COMPLETO_DO_PROJETO.md): Manual exaustivo cobrindo arquitetura, modelo matemático de conversão angular, protocolo serial, pacotes de bytes do `SyncWrite` e decisões de projeto.
- 🏛️ [**Arquitetura e Fluxos**](docs/ARCHITECTURE.md): Diagramas de sequência, responsabilidades das camadas, invariantes de domínio e tratamento defensivo de erros.
- 📦 [**Referência de Módulos e APIs**](docs/MODULES.md): Assinatura de métodos, parâmetros, contratos de retorno e exceções de cada módulo do sistema.
- 📋 [**Registro e Auditoria de Calibração**](docs/CALIBRATION_LOG.md): Tabela auditável com todas as medições de encoder, zeros mecânicos, sentidos de rotação e batentes físicos das 6 juntas.
- ⚡ [**Guia de Comandos e Operação**](docs/COMMANDS_AND_TESTING_GUIDE.md): Referência rápida de todas as linhas de comando, opções e comportamentos operacionais.
- 🛡️ [**Segurança e Boas Práticas**](docs/SAFETY_AND_TESTING.md): Protocolos de energização, mitigação de colisão, proteção de torque e manuseio de bancada.
- 📐 [**Procedimento de Calibração Manual**](docs/CALIBRATION.md): Metodologia passo a passo para levantamento de parâmetros de novos servomotores.
- 🗺️ [**Plano de Evolução**](PLAN.md): Roadmap técnico e evolução planejada para controle cartesiano e cinemática.
- ✅ [**Tarefas e Progresso**](TASKS.md): Histórico de etapas concluídas e critérios de aceite.

---

## ⚠️ Diretrizes de Segurança para Operação

1. **Sustentação Estrutural:** Nunca habilite ou desabilite torque sem garantir que os elos do braço estão apoiados mecanicamente ou em posição estável.
2. **Área Desobstruída:** Mantenha um raio mínimo de **60 cm livre** ao redor da base do robô durante qualquer teste motorizado.
3. **Corte de Emergência:** O operador deve manter acesso físico imediato ao interruptor da fonte de alimentação de bancada (7.4V - 12V) ou à interrupção via `Ctrl+C`.
4. **Alívio de Carga:** Ao energizar o robô pela primeira vez na sessão, forneça leve suporte manual para absorver o ajuste inicial de torque.
5. **Velocidade Controlada:** Inicie sempre novos testes com velocidades reduzidas (`speed <= 400`, `acc <= 30`), conforme configurado em `robot_config.py`.
