# Relatório Técnico: Padronização da Camada de Teleoperação e Controle PS5

**Data:** 01 de setembro de 2026  
**Status:** Proposta de Padronização / Pré-Refatoração  
**Escopo:** `src/actions/tele_control/ps5_controller.py`, `src/infrastructure/input/ps5_controller.py`, `src/application/teleoperation.py`, `src/application/ports/control_input.py`, `src/application/robot_arm.py`, `src/application/joint.py`.

---

## 1. Estado Atual

### 1.1 Fluxo Real vs. Fluxo Teórico

O fluxo teórico previsto na documentação e nos contratos de portas propõe uma separação limpa entre captura de entrada física, orquestração de controle manual e coordenação do robô:

```text
[Teórico]
DualSense → evdev → Ps5ControllerInput → ControlState → TeleOperation → RobotArm → Joint → ServoBus
```

No entanto, a análise do código executável atual (`src/actions/tele_control/ps5_controller.py`, `src/actions/tele_control/keyboard_control.py` e `src/application/teleoperation.py`) revela um fluxo diferente:

```text
[Fluxo Real Executável]
DualSense (Hardware)
   │
   ├── evdev (/dev/input/eventN)
   │     ↓
   │   Ps5ControllerInput (Infrastructure)
   │     ↓ [retorna ControlState com flags de política: movement_enabled, emergency_stop, delta_time]
   │
   └── hidraw (DualSense HID)
         ↓
       adaptive_trigger / dualsense_color (Utils)
         ▲
         │ (chamadas diretas do loop)
         │
   run_control_loop (src/actions/tele_control/ps5_controller.py)
   [Orquestrador monolítico na camada de Actions; TeleOperation é um stub não utilizado]
   ├── Coleta de métricas via WebSocket (síncrono/tentativa a cada 500 ms)
   ├── Detecção de inatividade (10 s) e alteração de cor RGB do controle
   ├── Detecção de duplo clique no L2 para auto-close da garra
   ├── Cálculo de integração de jog: target_angles += SPEED * dt * axis
   ├── Clamping manual de limites angulares por junta
   ├── Lógica de validação de carga da garra (validate_load) e detecção de objeto
   ├── Gravação de logs de calibração em arquivo de texto
   └── Chamadas não coordenadas: Joint.command() junta a junta
         ↓
       Joint (Application)
         ↓
       ScServoBus (Infrastructure) → scservo_sdk → Hardware Real
```

### 1.2 Principais Divergências Identificadas

1. **`TeleOperation` (`src/application/teleoperation.py`) desconectada:** A classe de domínio que deveria orquestrar a teleoperação é atualmente um esqueleto vazio. O controle real é executado por uma função procedural de 470 linhas dentro da camada de *actions*.
2. **Duplicação de loop de controle:** `src/actions/tele_control/keyboard_control.py` implementa seu próprio `run_control_loop` com lógica de jog, `delta_time`, clamping de ângulos e tratamento de emergência duplicados, além de instanciar suas próprias configurações de juntas.
3. **Adapter com decisões de aplicação:** `Ps5ControllerInput` gerencia internamente se o robô pode se mover (`movement_enabled`), se está em parada de emergência (`emergency_stop`) e calcula `delta_time`, misturando leitura de hardware com política de segurança do sistema.
4. **Vazamento de regras da garra para o `RobotArm`:** As flags `_atuator_object` e `_close_gripper_ability_active` foram inseridas diretamente em `RobotArm`, acoplando o conceito genérico do braço a uma mecânica específica de uma única ferramenta terminal.

---

## 2. Inventário de Responsabilidades

Identificamos 19 responsabilidades distintas distribuídas entre o adapter, a action, o núcleo do robô e utilitários:

1. **Descoberta de dispositivo (`find_ps5_controller_device`):** Varredura de `/dev/input/event*`, filtragem por nome de dispositivo (excluindo touchpad e sensores de movimento), detecção de permissões e ambiguidades.
2. **Ciclo de vida e conexão (`open`, `close`, `is_available`):** Abertura de `InputDevice`, liberação de file descriptors e detecção de desconexão abrupta via `OSError`.
3. **Decodificação de eventos de baixo nível `evdev`:** Tradução de constantes numéricas (`EV_KEY`, `EV_ABS`, `BTN_SOUTH`, `ABS_X`, etc.) em nomes amigáveis de botões e eixos.
4. **Rastreamento de estado de botões:** Manutenção dos conjuntos transitórios `buttons_pressed`, `buttons_held` e `buttons_released`.
5. **Normalização de analógicos:** Mapeamento de sticks de [0, 255] para [-1.0, 1.0] com inversão do eixo Y; mapeamento de triggers [0, 255] para [0.0, 1.0].
6. **Filtro de Deadzone Radial 2D:** Aplicação de zona morta radial (`_radial_stick_deadzone`) para sticks analógicos com reescalonamento contínuo da magnitude.
7. **Cálculo de `delta_time`:** Cálculo do tempo decorrido entre leituras sucessivas do controle usando `time.monotonic()`.
8. **Detecção de duplo acionamento (`TriggerDoublePressDetector`):** Detecção temporal e por limiar de borda para dois toques rápidos consecutivos em eixos analógicos ou botões.
9. **Lógica de Habilitação de Movimento (Arm/Disarm):** Alternância do estado de movimento pelo botão PS.
10. **Lógica de Parada de Emergência (Emergency Stop):** Detecção de duplo clique no botão Círculo, retenção do estado de emergência e desligamento de torque de emergência.
11. **Mapeamento de Entradas para Articulações (Bindings):** Associação fixa de eixos analógicos/D-pad para juntas específicas (`base_yaw`, `shoulder_pitch`, `elbow_pitch`, `wrist_pitch`, `wrist_roll`, `gripper`).
12. **Integração de Jog Temporal:** Cálculo de alvos de ângulo (`target_angle += SPEED * dt * intensity`).
13. **Clamping de Limites Físicos:** Restrição de alvos dentro de `[min_angle, max_angle]` de cada junta.
14. **Coordenação e Envio de Comandos de Movimento:** Chamadas discretas para cada `joint.command()`.
15. **Detecção de Objeto e Carga na Garra:** Avaliação de esforço dinâmico (`validate_load`) contra corrente, velocidade e erro angular, retenção de posição ao agarrar.
16. **Habilidade de Fechamento Automático da Garra (Auto-Close):** Máquina de estados para fechar a garra automaticamente, pausar em caso de obstrução e retomar caso a carga normalize.
17. **Feedback Tátil Adaptativo (Adaptive Triggers):** Aplicação de resistência no gatilho L2 proporcional à carga excedente da garra via conexão HID.
18. **Feedback Visual RGB (Lightbar):** Atualização da cor do LED do controle de acordo com o estado do sistema (desabilitado/habilitado/ocioso após 10 s).
19. **Telemetria e Streaming de Métricas:** Envio periódico (500 ms) do snapshot térmico, elétrico e mecânico para `ws://localhost:2399/metrics`.

---

## 3. Matriz de Responsabilidades

| # | Responsabilidade | Está Hoje Em | Deveria Ficar Em | Motivo Arquitetural / Robótico |
|---|---|---|---|---|
| 1 | Descoberta de dispositivo | `Ps5ControllerInput` / infra | `Ps5ControllerInput` / infra | Detalhe específico de plataforma Linux (`evdev`). |
| 2 | Ciclo de vida e desconexão | `Ps5ControllerInput` / infra | `Ps5ControllerInput` / infra | Gerência de conexão de I/O de baixo nível. |
| 3 | Tradução de eventos evdev | `Ps5ControllerInput` / infra | `Ps5ControllerInput` / infra | Responsabilidade do adapter de hardware de entrada. |
| 4 | Rastreamento de botões | `Ps5ControllerInput` / infra | `Ps5ControllerInput` / infra | Formação do snapshot físico do dispositivo. |
| 5 | Normalização de eixos | `Ps5ControllerInput` / infra | `Ps5ControllerInput` / infra | Entrega valores adimensionais [-1.0, 1.0] padronizados. |
| 6 | Deadzone radial | `Ps5ControllerInput` / infra | `Ps5ControllerInput` / infra | Compensação física inerente ao sensor do joystick. |
| 7 | Cálculo de `delta_time` | `Ps5ControllerInput` / infra | `TeleOperation` (Application) | O passo temporal pertence ao orquestrador do loop de controle, não ao periférico de entrada. |
| 8 | Detecção de duplo acionamento | `Ps5ControllerInput` / infra | `src/utils` ou `input_processing` | Utilitário desacoplado de processamento de sinais de entrada. |
| 9 | Habilitação de movimento | `Ps5ControllerInput` / infra | `TeleOperation` (Application) | Regra de segurança operacional pertencente à aplicação. |
| 10 | Política de Emergência | `Ps5ControllerInput` + Action | `TeleOperation` + `RobotArm` | Parada segura e desativação de atuadores são responsabilidades do núcleo do robô. |
| 11 | Mapeamento Input → Juntas | `run_control_loop` (Action) | `TeleOperation` (via Mapper/Profile) | Permite alternar perfis de controle (ex: teclado, gamepad, modos invertidos) sem duplicar código. |
| 12 | Integração de Jog no tempo | `run_control_loop` (Action) | `TeleOperation` (Application) | Geração de comando contínuo discreto a partir de sinais normalizados e tempo. |
| 13 | Clamping de limites angulares | `run_control_loop` (Action) | `RobotArm` / `Joint` (Application) | A proteção contra comandos fora do envelope físico é invariante do modelo do robô. |
| 14 | Envio de comandos de movimento | `run_control_loop` (Action) | `RobotArm` (Application) | O robô deve oferecer API de pose/jog coordenada (`jog_joints` ou `command_pose`). |
| 15 | Detecção de carga na garra | `run_control_loop` (Action) | `GripperService` ou Habilidade de Aplicação | Regra de comportamento funcional da ferramenta, não do script de controle. |
| 16 | Habilidade de fechamento da garra | `run_control_loop` + `RobotArm` | `GripperAbility` / `TeleOperation` | Comportamento de automação de alto nível. |
| 17 | Feedback Tátil (Gatilhos) | `run_control_loop` + `utils` | `TeleOperation` + Feedback Adapter | Orquestrado na aplicação via abstração/porta de feedback tátil. |
| 18 | Feedback Visual (LED RGB) | `run_control_loop` + `utils` | `TeleOperation` + Feedback Adapter | Mudança de cor reflete o estado da aplicação (`TeleOperation`). |
| 19 | Streaming de métricas (WebSocket) | `run_control_loop` (Action) | Telemetry Service / Observer | Não deve bloquear o loop de controle de tempo real (50 Hz). |

---

## 4. Contrato do `ControlState`

O `ControlState` atual define os seguintes campos:

```python
@dataclass
class ControlState:
    axes: Mapping[str, float] = field(default_factory=dict)
    buttons_pressed: frozenset[str] = field(default_factory=frozenset)
    buttons_held: frozenset[str] = field(default_factory=frozenset)
    buttons_released: frozenset[str] = field(default_factory=frozenset)
    timestamp: float = 0.0
    delta_time: float = 0.0
    movement_enabled: bool = False
    emergency_stop: bool = False
```

### 4.1 Análise Crítica dos Campos

* **`axes` (Manter):** Representa sinais contínuos analógicos normalizados (`left_x`, `left_y`, `l2`, `r2`, etc.). É dado físico puro.
* **`buttons_pressed`, `buttons_held`, `buttons_released` (Manter):** Eventos discretos e estado instantâneo dos botões físicos. Essencial para diferenciar disparos pontuais de ações sustentadas.
* **`timestamp` (Manter):** Marca temporal monotônica em que o dispositivo foi amostrado. Fundamental para auditoria e controle.
* **`delta_time` (Redesenhar / Remover do `ControlState`):**
  * *Problema:* `delta_time` representa o intervalo entre iterações do orquestrador de controle. Se o dispositivo for lido duas vezes no mesmo tick ou se houver múltiplos dispositivos de entrada, o tempo de integração pertence ao ciclo de controle da aplicação, não à mensagem do periférico.
  * *Recomendação:* `TeleOperation` deve calcular e manter o `dt` do seu próprio loop (`step(dt)`).
* **`movement_enabled` (Remover do `ControlState`):**
  * *Problema:* `movement_enabled` é um estado operacional da aplicação (robô armado vs. desarmado). O controle físico emite apenas "botão PS pressionado". Ao colocar a flag no adapter, impede-se que outra interface (ex: teclado ou GUI) arme o robô de forma compartilhada.
  * *Recomendação:* O adapter emite o evento de botão; `TeleOperation` gerencia a máquina de estados de armação.
* **`emergency_stop` (Redesenhar):**
  * *Problema:* Mistura o *gatilho de entrada de emergência* (ex: operador apertou duplo círculo ou ESC) com o *estado latched de emergência do robô*.
  * *Recomendação:* O `ControlState` pode conter flags de entrada ou eventos puros (ex: `"emergency_stop" in buttons_pressed`). O estado de emergência latched e as ações de desligamento seguro pertencem a `TeleOperation` e `RobotArm`.

---

## 5. Responsabilidade da `TeleOperation`

A classe `TeleOperation` (`src/application/teleoperation.py`) deve ser o **orquestrador central de controle manual** do sistema.

### 5.1 Ciclo de Responsabilidade de `TeleOperation`

```text
1. Ler ControlInput.read()
2. Verificar e processar gatilhos de parada de emergência
3. Atualizar máquina de estados de segurança (Habilitado / Desabilitado / Ocioso)
4. Mapear entradas físicas em intenções de movimento através de um Profile/Mapper
5. Integrar intenções de movimento no tempo usando dt determinístico
6. Delegar movimentação coordenada para RobotArm
7. Atualizar serviços de feedback periférico (LEDs, triggers hápticos)
```

### 5.2 O que NÃO Pertence a `TeleOperation`

* Leitura direta de `evdev`, portas seriais ou sockets de rede.
* Detalhes de registradores e comunicação com servos (`ServoBus` / `scservo_sdk`).
* Conversão entre graus e contagens de encoder (`JointConfig`).
* I/O blocante no disco (arquivos de log) ou chamadas de rede síncronas (WebSockets).

---

## 6. Responsabilidade do `RobotArm`

O `RobotArm` representa o modelo agregado e coordenado do manipulador robótico.

### 6.1 Estado Atual e Acoplamentos Indesejados

Atualmente, `RobotArm` possui atributos introduzidos durante experimentos de teleoperação:
* `_atuator_object`: flag booleana que indica se a garra está em contato/apertando um objeto.
* `_close_gripper_ability_active`: flag booleana que indica se uma automação de fechamento de garra está em execução.

Essas propriedades são específicas de uma ferramenta terminal (garra com sensor de carga) e violam a generalidade de `RobotArm` como manipulador de N juntas.

### 6.2 Capacidades Necessárias no `RobotArm` para Teleoperação

1. **Jog multi-junta coordenado:** Capacidade de aplicar variações angulares $\Delta\theta$ a um subconjunto ou a todas as juntas com validação atômica de limites.
2. **Clamping centralizado de segurança:** Garantir que nenhum comando enviado via jog ultrapasse `[min_angle, max_angle]`.
3. **Parada e desativação segura:** Método unificado de emergência (`emergency_stop()`) que desabilita torque e cancela movimentos em andamento.
4. **Consulta unificada de segurança:** Validação de sobrecarga (`is_movement_safe`) baseada em limites físicos de todas as juntas.

---

## 7. Responsabilidade de `Joint`

A classe `Joint` deve permanecer restrita à gerência de **uma única articulação**:

```text
TeleOperation ──(intenção / jog)──> RobotArm ──(comando coordenado)──> Joint ──(protocolo)──> ServoBus
```

* **Pertence a `Joint`:**
  * Conversão de unidades (graus $\leftrightarrow$ counts) através de `JointConfig`.
  * Verificação de limites de carga e status térmico/elétrico individual (`is_load_safe`, `get_status`).
  * Envio atômico de comando não-bloqueante (`command`) ou movimento monitorado (`move`).
* **NÃO pertence a `Joint`:**
  * Lógica de controle de gamepad ou teclado.
  * Integração de velocidade temporal no loop de teleoperação.
  * Conhecimento sobre outras juntas do braço.

---

## 8. Código Experimental vs. Código Consolidado

### 8.1 Pode Permanecer Praticamente Como Está (Consolidado)

* `find_ps5_controller_device`: Descoberta automática de dispositivo `evdev`.
* `JointConfig`: Modelo de configuração e conversão cinemática angular pura.
* `Joint`: Encapsulamento atômico de uma junta sobre o `ServoBus`.
* `ScServoBus` e `ServoBus`: Porta e adapter de comunicação serial STS.
* `DualSenseColorConfig` e `set_dualsense_color`: Abstração de cores e envio HID da barra de luz.
* Normalização e Deadzone Radial 2D em `Ps5ControllerInput`.

### 8.2 Precisa Ser Movido (Localização Incorreta)

* **`TriggerDoublePressDetector`:** Mover de `src/infrastructure/input/ps5_controller.py` para um utilitário reutilizável de processamento de entrada (ex: `src/utils/input_detector.py`).
* **Lógica de Jog e Clamping:** Mover de `run_control_loop` (action) para `TeleOperation` e `RobotArm`.
* **Detecção de Inatividade (Timeout de 10s):** Mover da action para `TeleOperation`.
* **Streaming de Métricas WebSocket:** Mover de `run_control_loop` para um serviço ou observer de telemetria assíncrono.

### 8.3 Precisa Ser Redesenho (Contrato / Responsabilidade Inadequada)

* **`ControlState`:** Remover `movement_enabled`, `emergency_stop` e `delta_time`, mantendo-o como snapshot puro de eventos físicos.
* **`run_control_loop` procedural na Action:** Migrar a lógica para a classe `TeleOperation` dentro de `src/application/`.
* **Atributos de garra em `RobotArm` (`_atuator_object`, `_close_gripper_ability_active`):** Extrair para um componente ou estado de habilidade gerenciado na camada de aplicação.

---

## 9. Padronizações Antes das Próximas Features

Antes de implementar novas funcionalidades (como controle cartesiano de efetuador, interpolação de trajetória contínua ou múltiplos modos de controle), as seguintes padronizações devem estar concluídas:

1. **Contrato de Entrada Estável (`ControlInput` / `ControlState`):** O formato dos dados emitidos por qualquer periférico (PS5, Teclado, Joystick genérico) deve ser consistente e livre de estados internos da aplicação.
2. **Motor de Teleoperação Unificado (`TeleOperation`):** `TeleOperation` deve ser o único ponto que executa o loop de controle manual a 50 Hz, consumindo qualquer `ControlInput` injetado.
3. **Mapeador de Controle Configurável (Input Mapper / Bindings):** Mapeamento desacoplado entre eixos/botões e comandos de jog do robô.
4. **Isolamento de Efeitos Colaterais:** I/O de disco (arquivos de calibração) e de rede (WebSockets) devem ser desacoplados do loop de controle em tempo real.

---

## 10. Ordem Recomendada das Refatorações

A evolução deve ser estritamente incremental, protegida por testes automatizados em cada etapa:

```text
Refatoração 01: Purificação do Contrato do ControlState e Ps5ControllerInput
      ↓
Refatoração 02: Implementação do Núcleo da TeleOperation
      ↓
Refatoração 03: Desacoplamento do Mapeamento de Entradas (Control Profiles)
      ↓
Refatoração 04: Limpeza do RobotArm e Extração das Habilidades de Garra
      ↓
Refatoração 05: Integração da Action com a Nova TeleOperation
```

---

### Detalhamento das Etapas

#### Refatoração 01 — Purificação do Contrato do `ControlState` e `Ps5ControllerInput`
* **Objetivo:** Remover flags de política (`movement_enabled`, `emergency_stop`, `delta_time`) do `ControlState` e do adapter PS5, mantendo o adapter estritamente responsável por ler, normalizar e emitir eventos de hardware.
* **Arquivos Envolvidos:** `src/application/ports/control_input.py`, `src/infrastructure/input/ps5_controller.py`, `tests/test_ps5_controller.py`.
* **Responsabilidade Corrigida:** Isolamento do adapter de infraestrutura em relação às regras de negócio.
* **Testes de Proteção:** `tests/test_ps5_controller.py` ajustado para validar que o adapter entrega eixos e botões sem gerenciar estados da aplicação.
* **Critério de Conclusão:** O adapter PS5 não mantém variáveis de estado do robô; todos os testes de entrada passam.

---

#### Refatoração 02 — Implementação do Núcleo da `TeleOperation`
* **Objetivo:** Implementar os métodos `step(dt)` e `run(frequency)` em `src/application/teleoperation.py` para gerenciar a máquina de estados (Habilitado/Desabilitado/Emergência), integração de tempo e disparo de comandos.
* **Arquivos Envolvidos:** `src/application/teleoperation.py`, novo `tests/test_teleoperation.py`.
* **Responsabilidade Corrigida:** Centralização da orquestração de controle manual na camada de aplicação.
* **Testes de Proteção:** Testes unitários com `FakeControlInput` e `FakeServoBus` simulando ticks de controle, transições de estado e parada de emergência.
* **Critério de Conclusão:** `TeleOperation.step(dt)` executa ciclos de controle determinísticos e testáveis sem dependência de hardware real.

---

#### Refatoração 03 — Desacoplamento do Mapeamento de Entradas (Control Profiles)
* **Objetivo:** Criar abstração simples para mapear botões/eixos em comandos de jog (graus/s) por junta, eliminando `if/elif` manuais e permitindo alternar configurações (ex: modo normal vs. invertido).
* **Arquivos Envolvidos:** `src/application/teleoperation.py`, `src/infrastructure/input/`.
* **Responsabilidade Corrigida:** Separação entre a intenção de entrada e a aplicação do movimento nas juntas.
* **Testes de Proteção:** Testes unitários validando mapeamentos de diferentes layouts de controle.
* **Critério de Conclusão:** Teclado e PS5 utilizam a mesma engine de `TeleOperation`, alterando apenas o profile de entrada.

---

#### Refatoração 04 — Limpeza do `RobotArm` e Extração das Habilidades de Garra
* **Objetivo:** Remover `_atuator_object` e `_close_gripper_ability_active` de `RobotArm`, transferindo a lógica de detecção de carga e auto-fechamento para um serviço ou extensão de habilidade na camada de aplicação.
* **Arquivos Envolvidos:** `src/application/robot_arm.py`, `tests/test_robot_arm.py`, novo módulo de habilidade da garra.
* **Responsabilidade Corrigida:** Coesão da classe `RobotArm`.
* **Testes de Proteção:** `tests/test_robot_arm.py` e testes dedicados à automação da garra.
* **Critério de Conclusão:** `RobotArm` lida unicamente com a coordenação de juntas; automações de ferramentas ficam desacopladas.

---

#### Refatoração 05 — Integração da Action com a Nova `TeleOperation`
* **Objetivo:** Simplificar `src/actions/tele_control/ps5_controller.py` e `keyboard_control.py` para atuarem apenas como *Composition Roots* locais da ação, instanciando `TeleOperation`, adapters e executando `teleop.run()`.
* **Arquivos Envolvidos:** `src/actions/tele_control/ps5_controller.py`, `src/actions/tele_control/keyboard_control.py`, `src/actions/router.py`.
* **Responsabilidade Corrigida:** Camada de actions atua apenas como ponto de entrada e montagem.
* **Testes de Proteção:** Testes de integração e suíte completa automatizada (`tests/test_actions.py`).
* **Critério de Conclusão:** Menos de 50 linhas em cada arquivo de action de teleoperação; zero duplicação de lógica de controle.

---

## 11. Riscos Identificados

### 11.1 Riscos Físicos e de Robótica
* **Runaway por `delta_time` instável:** Se o cálculo de `dt` sofrer saltos (ex: durante bloqueio temporário de I/O), o cálculo de jog ($\Delta\theta = v \cdot \Delta t$) pode produzir saltos angulares perigosos no braço real. É mandatório aplicar um teto máximo para $\Delta t$ (ex: `dt = min(dt, 0.05)`).
* **Desconexão do periférico durante movimento ativo:** Se o operador estiver inclinando o stick e o controle perder conexão (Bluetooth/cabo), o robô deve parar imediatamente e desabilitar torque por watchdog, evitando movimentos contínuos descontrolados.
* **Conflito de Emergência:** A parada de emergência física deve sempre ter precedência absoluta e zerar instantaneamente alvos e torques em hardware.

### 11.2 Riscos de Software e Concorrência
* **Jitter e latência no loop de controle:** Chamadas síncronas para WebSockets (`collect_metrics`) ou escritas em arquivos de texto inserem latências imprevisíveis no ciclo de 50 Hz. Essas operações devem ser assíncronas ou isoladas do thread de controle.
* **Perda de eventos transitórios:** Botões pressionados e soltos rapidamente em um único intervalo de leitura precisam ser garantidos pelo snapshot sem risco de *race conditions*.

---

## 12. Decisões Pendentes

As seguintes decisões de arquitetura e design devem ser alinhadas antes da implementação:

### Decisão Pendente 01: Onde deve residir a gestão de Habilidades Específicas de Ferramenta (Garra Inteligente)?
* **Alternativa A (Recomendada):** Criar um componente de aplicação `GripperController` / `GripperAbility` que observa o `RobotArm` e o `TeleOperation`, mantendo `RobotArm` genérico.
* **Alternativa B:** Manter métodos utilitários no `RobotArm` específicos para a junta `'gripper'`.
* *Trade-off:* A Alternativa A preserva a coesão do braço e permite trocar a garra por outro efetuador futuro sem alterar a classe central do robô.

### Decisão Pendente 02: Como gerenciar o streaming de telemetria sem degradar o loop de 50 Hz?
* **Alternativa A (Recomendada):** Observer assíncrono com fila `queue.Queue` ou thread separada para despacho WebSocket.
* **Alternativa B:** Despacho direto não-bloqueante com timeout curto (como é feito hoje, mas com risco residual de jitter).
* *Trade-off:* A Alternativa A garante jitter zero no loop de controle, com custo de uma thread adicional simples.

---

## 13. Definition of Done (DoD) para a Padronização

A camada de teleoperação será considerada padronizada e pronta para novas features quando atender a todos os seguintes critérios:

1. **`TeleOperation` como orquestrador único:** Nenhuma action ou script procedural executa loops próprios de integração de jog ou controle manual.
2. **Adapter `Ps5ControllerInput` puro:** O adapter não contém variáveis de estado operacional do robô (`movement_enabled`, `emergency_stop`) nem cálculo de `delta_time`.
3. **Contrato de `ControlInput` agnóstico:** Teclado, controle PS5 e futuros dispositivos implementam a mesma interface e podem ser alternados sem modificar a aplicação.
4. **`RobotArm` coeso:** Remoção de atributos e flags específicas de garra do núcleo do braço robótico.
5. **Cobertura de testes automatizados sem hardware:** Toda a orquestração de `TeleOperation`, máquinas de estado e perfis de controle é coberta por testes unitários com test doubles (`FakeControlInput`, `FakeServoBus`).
6. **Zero chamadas blocantes no loop de 50 Hz:** Logs e telemetria isolados do fluxo de controle em tempo real.
