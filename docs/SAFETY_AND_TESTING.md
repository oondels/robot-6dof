# Segurança, calibração e testes

## Princípio geral

Software validado não torna um braço fisicamente seguro por si só. Erros de
calibração, montagem, alimentação, IDs ou sentido podem produzir colisões e
quedas mesmo quando todos os testes passam.

## Estado seguro atual

`robot_config.py` contém:

```python
JOINT_CONFIGS: tuple[JointConfig, ...] = ()
```

Enquanto estiver vazio, `main()` lança `RuntimeError` antes de criar a porta.
Não substitua essa tupla por valores de exemplo usados nos testes.

## Antes de energizar

1. Fixe ou apoie o braço para que nenhuma junta caia ao perder torque.
2. Deixe livre todo o volume de movimento.
3. Confirme alimentação, aterramento, baudrate e porta.
4. Confirme que cada servo possui ID individual; `254` é broadcast.
5. Trabalhe com apenas uma junta nova por vez.
6. Comece com velocidade e aceleração reduzidas.
7. Tenha um meio físico imediato de cortar alimentação.
8. Não permaneça dentro do volume alcançável do braço.

## Torque

`Joint.enable_torque()` lê a posição atual e a grava como alvo antes de
habilitar o registrador de torque. Essa sequência reduz saltos causados por um
alvo antigo, mas não protege contra:

- leitura incorreta do encoder;
- configuração de modo incorreta;
- montagem sob carga;
- perda de comunicação depois da habilitação;
- limites mecânicos incorretos.

`disable_torque()` pode fazer uma junta sustentando peso cair. A política
planejada para falhas de movimento é manter torque e abortar a operação; o
desligamento deve ser explícito e fisicamente supervisionado.

## Calibração planejada

A calibração será manual e não buscará batentes automaticamente:

1. Desabilitar torque e apoiar a estrutura.
2. Colocar a junta na referência física escolhida como `0°`.
3. Ler e registrar `zero_position`.
4. Fazer pequeno deslocamento no sentido físico positivo.
5. Se os counts aumentarem, usar `direction=1`; se diminuírem, `direction=-1`.
6. Medir limites conservadores, deixando margem antes dos batentes.
7. Verificar se ambos os extremos convertidos ficam em `0..4095`.
8. Testar pequenos comandos antes de ampliar o intervalo.

Intervalos que atravessam a volta do encoder não são aceitos atualmente.

## Limites operacionais conhecidos

| Parâmetro | Intervalo aceito |
| --- | --- |
| posição | `0..4095` counts |
| ID individual | `0..253` |
| velocidade | `0..3400` |
| aceleração | `0..254` |
| direção | `-1` ou `1` |
| tolerância angular | maior que `0°` |

Internamente, a tolerância angular é arredondada para counts e nunca fica abaixo
de um count. Essa tolerância numérica não substitui margens mecânicas de
segurança.

Uma posição dentro da tolerância não prova, isoladamente, que o movimento foi
concluído com segurança. A conclusão futura combinará posição, `ReadMoving` e
timeout.

Esses limites validam o formato do comando; os limites mecânicos reais devem
ser mais restritivos e específicos para cada junta.

## Testes sem hardware

Execute:

```bash
python -m unittest discover -s tests -v
```

A suíte deve ser executada antes e depois de qualquer mudança. Ela não deve:

- importar ou criar `PortHandler` para testes unitários;
- abrir `/dev/ttyUSB0`;
- depender de posição física;
- exigir torque;
- usar atrasos reais longos.

## Como usar `FakeServo`

Construção básica:

```python
servo = FakeServo(position=2048, moving=0)
joint = Joint(servo=servo, config=config)
```

Verificação de comando:

```python
joint.command(45)
assert servo.position_commands == [
    (config.servo_id, target, config.speed, config.acc)
]
```

Simulação de movimento futuro:

```python
servo.queue_motion(
    positions=[2100, 2200, 2300],
    moving_states=[1, 1, 0],
)
```

Cada chamada a `ReadPosSpeed` consome uma posição; cada chamada a `ReadMoving`
consome um estado. Quando a sequência termina, o último valor é mantido.

## Canais de erro do SDK

Cada operação pode falhar de duas formas:

```text
result != COMM_SUCCESS  → transporte/barramento
error != 0              → erro informado pelo servo
```

Ambos devem passar por `validate_result`. Um comando aceito pelo barramento não
prova que o servo chegou ao destino.

## Limitações conhecidas no snapshot atual

- `Joint.command()` não aguarda conclusão; retornar o alvo não comprova chegada.
- `Joint.move()` está temporariamente ausente até existir espera com timeout.
- `Joint.movement_status()` combina uma leitura de posição, uma leitura de
  `ReadMoving` e a tolerância, mas ainda não existe um laço de espera.
- Posição e movimento são lidos consecutivamente, não simultaneamente; o
  snapshot não substitui timeout nem leituras periódicas.
- Não existe `RobotArm` nem movimento sincronizado.
- `JOINT_CONFIGS` está vazio porque nenhuma calibração física foi registrada.
- Mensagens operacionais usam `print`, não logging estruturado.
- Não há teste integrado com porta e servo reais.
- Não há compensação de gravidade ou detecção de colisão.
- A lista de dependências ainda não foi reduzida ao mínimo necessário.

## Critério para teste físico futuro

Um teste no hardware só deve ocorrer quando:

- todos os testes unitários passam;
- a junta possui configuração medida, não estimada;
- o comando possui timeout e diagnóstico;
- o braço está apoiado e a área está livre;
- o teste começa com deslocamento, velocidade e aceleração pequenos;
- o operador consegue cortar alimentação imediatamente.
