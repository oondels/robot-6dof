# Arquitetura

## Objetivo

O projeto usa uma Clean Architecture pragmática: o núcleo do controle conhece
as intenções necessárias para operar servos, mas não conhece nomes, retornos ou
registradores do `scservo_sdk`.

```text
main.py / actions / calibration
              │
              ▼
       Joint e RobotArm
              │
              ▼
     ServoBus (Protocol)
              ▲
              │ implementa
         ScServoBus
              │
              ▼
        scservo_sdk
```

A regra de dependência é:

```text
infrastructure → application
```

O núcleo `application` não importa `infrastructure` nem `scservo_sdk`.

## Organização

```text
src/
├── application/
│   ├── joint.py
│   ├── joint_config.py
│   ├── kinematics.py
│   ├── movement_status.py
│   ├── robot_arm.py
│   └── ports/
│       └── servo_bus.py
├── infrastructure/
│   ├── kinematics_loader.py
│   └── scservo_bus.py
├── actions/
├── calibration/
└── utils/
```

Não existe uma pasta `domain/` neste estágio. Criá-la sem uma fronteira nova
apenas aumentaria a estrutura física sem reduzir acoplamento real.

## Responsabilidades

### `JointConfig`

Configuração imutável de uma junta calibrada. Contém identidade, zero físico,
direção, limites, velocidade, aceleração e tolerância. Faz conversões puras
entre graus e counts e não conhece comunicação ou hardware.

### `MovementStatus`

Fotografia imutável de uma observação de movimento: alvo, posição atual, erro,
flag de movimento e resultado da tolerância.

### `Joint`

Representa uma junta operacional. Usa `JointConfig` para regras físicas e
`ServoBus` para leitura e comando. Coordena políticas do sistema, incluindo:

- preparar a posição atual antes de habilitar torque;
- confirmar habilitação e desabilitação;
- validar parâmetros antes de enviar movimento;
- distinguir chegada, parada fora do alvo e timeout.

`Joint` não conhece `ReadPosSpeed`, `WritePosEx`, `COMM_SUCCESS`, endereço de
registrador ou formato de erro do SDK.

### `RobotArm`

Agrega juntas, valida nomes e IDs únicos, coordena torque coletivo e envia poses
sincronizadas por `ServoBus.command_positions_sync()`. A política de pose fica no
núcleo; o empacotamento do `SyncWrite` fica no adaptador.

### Cinemática direta offline

`application/kinematics.py` representa a geometria DH separadamente da calibração
de `JointConfig`. Recebe ângulos físicos por nome e retorna a transformação final,
posição, rotação e transformações acumuladas. Usa somente a biblioteca padrão,
sem ler encoders ou conhecer `RobotArm`, `ServoBus` ou o SDK.

`infrastructure/kinematics_loader.py` lê diretamente um `kinematics.yml` com
PyYAML e constrói uma configuração validada. Não inicia o sistema de perfis:
`arm_profile.py` e `profile.yml` continuam sem implementação.

```text
kinematics.yml → carregador → KinematicConfig ─┐
                                            ├→ forward_kinematics → resultado
dicionário de ângulos físicos em graus ───────┘
```

Uma aplicação pode obter os ângulos com `RobotArm.current_angles()` e selecionar
explicitamente as juntas da cadeia antes do cálculo. Essa leitura é separada da
matemática e não ocorre na API offline. O núcleo não reaplica `direction`.

Contrato, convenção, frames e exemplo executável estão no
[guia de cinemática direta](FORWARD_KINEMATICS.md).

### `ServoBus`

Porta de saída definida pelo núcleo como `Protocol`. Seu contrato usa intenções
do sistema:

```text
read_position
is_moving
command_position
is_torque_enabled
enable_torque
disable_torque
command_positions_sync
```

### `ScServoBus`

Adaptador de infraestrutura que traduz a porta para `scservo_sdk`:

```text
read_position             → ReadPosSpeed
is_moving                 → ReadMoving
command_position          → WritePosEx
torque                    → read1ByteTxRx/write1ByteTxRx
command_positions_sync    → SyncWritePosEx/groupSyncWrite
```

Também converte `result` e `error` do SDK em exceções Python.

### `main.py`

Composition Root. É o único ponto da aplicação principal que monta as
implementações concretas:

```text
PortHandler
   ↓
sms_sts
   ↓
ScServoBus
   ↓
Joint(s)
   ↓
RobotArm
```

Criar os objetos não habilita torque nem envia movimento.

## Calibração

Os leitores de calibração bruta podem acessar `ReadPosSpeed` diretamente porque
existem antes de uma `JointConfig` confiável. Essa é uma exceção consciente e
restrita: essas rotinas não habilitam torque e não enviam posição.

As ferramentas que movimentam juntas ou poses usam `ScServoBus`, `Joint` e
`RobotArm`, assim como a aplicação principal.

## Testes

Há dois níveis de test doubles:

- `FakeServoBus`: testa o núcleo pela porta, sem conhecer o SDK;
- `FakeServo`: simula o SDK para testar `ScServoBus` e fluxos integrados.

A sequência de validação para mudanças de movimento é:

```text
raciocínio
   ↓
teste unitário
   ↓
FakeServoBus / FakeServo
   ↓
teste controlado
   ↓
hardware real
```

## Comando, movimento e controle

```text
command()       envia um alvo e retorna imediatamente
move()          envia e aguarda uma condição terminal
command_pose()  envia vários alvos em um pacote sincronizado
move_pose()     envia a pose e monitora todas as juntas
```

Essas operações representam controle angular discreto. A cinemática direta
offline é uma responsabilidade matemática separada. Cinemática inversa,
trajetórias cartesianas e controle cartesiano permanecem fora desse fluxo e
não devem ser misturados ao adaptador de hardware.
