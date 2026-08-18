# Arquitetura

## Visão geral

O projeto separa configuração física, operação do hardware, composição da
aplicação e validação do protocolo:

```text
robot_config.py
      │ JointConfig(s) calibradas
      ▼
   main.py ───── cria ─────► Joint
      │                       │
      │ cria                  │ usa
      ▼                       ▼
 PortHandler ───────────► sms_sts/SDK
                              │
                              ▼
                      validate_result()
```

Nos testes, `FakeServo` ocupa o lugar do objeto `sms_sts`:

```text
Joint ── mesma interface esperada ──► sms_sts real
                                  └─► FakeServo
```

Isso é possível pelo duck typing do Python: `Joint` depende dos métodos usados,
e não de uma classe concreta do SDK.

## Fronteiras de responsabilidade

### `JointConfig`

Objeto imutável que representa uma junta calibrada. Ele concentra:

- identidade (`name`, `servo_id`);
- zero físico em counts (`zero_position`);
- direção positiva (`direction`, somente `1` ou `-1`);
- intervalo físico (`min_angle`, `max_angle`);
- padrões operacionais (`speed`, `acc`, `tolerance_deg`);
- validação da configuração;
- conversão pura entre ângulo físico e posição do encoder.

Ele não conhece porta serial, torque ou estado do motor.

### `Joint`

Objeto de tempo de execução que combina um `JointConfig` com um servo. Ele:

- encaminha identidade e padrões para `config` por propriedades;
- lê posição e converte a leitura em ângulo;
- consulta se o servo informa que está em movimento;
- habilita, verifica e desabilita torque;
- envia posição, velocidade e aceleração ao SDK;
- valida respostas de comunicação.

Ele não abre nem fecha a porta serial. Essa decisão pertence ao ponto de
composição da aplicação.

### `main.py`

É o composition root: valida se existem configurações, cria porta e SDK, cria as
juntas e garante fechamento da porta com `finally`.

No estado atual ele apenas lê e mostra posição/ângulo. Com `JOINT_CONFIGS` vazio,
falha antes de criar `PortHandler`, impedindo acesso acidental ao hardware.

### `utils.validation`

Transforma os dois canais de erro do SDK em exceções Python:

- `result != COMM_SUCCESS`: erro de transporte/comunicação;
- `error != 0`: erro reportado pelo pacote do servo.

## Modelo de coordenadas

### Counts

O servo usa 4096 posições discretas, numeradas de `0` a `4095`. Um count
corresponde aproximadamente a:

```text
360° / 4096 = 0,087890625°
```

### Ângulo físico

O código público trabalha em graus relativos ao zero mecânico da junta. A
conversão é:

```text
position = round(
    zero_position
    + direction * angle * 4096 / 360
)
```

Exemplo puramente didático:

```text
zero_position = 2048
direction     = 1
angle         = 90°

position = 2048 + 90 * 4096 / 360 = 3072
```

Se `direction = -1`, o mesmo ângulo positivo reduz os counts. Os valores usados
nos testes não são calibração real do braço.

### Quantização

Como a posição é inteira, uma conversão ângulo → posição → ângulo pode retornar
uma pequena diferença. O erro esperado pelo arredondamento é de no máximo meio
count, aproximadamente `0,04395°`.

### Limites

`JointConfig` exige:

- ID entre `0` e `253`; `254` é reservado para broadcast;
- `zero_position` entre `0` e `4095`;
- `direction` igual a `1` ou `-1`;
- `min_angle < max_angle` e `0°` dentro do intervalo;
- extremos convertidos dentro do encoder;
- velocidade entre `0` e `3400`;
- aceleração entre `0` e `254`;
- tolerância positiva e números angulares finitos;
- tolerância convertida para counts com mínimo de um count.

A tolerância usada nas futuras comparações de chegada é derivada por:

```text
tolerance_counts = max(
    1,
    round(tolerance_deg * 4096 / 360)
)
```

Assim, alvo, posição atual e tolerância usam a mesma unidade.

Intervalos que precisariam atravessar `4095 → 0` não são suportados na versão
atual.

## Fluxos atuais

### Construção

```text
JointConfig valida e congela os dados
            ↓
Joint recebe servo + JointConfig
            ↓
nenhuma comunicação ocorre no construtor
```

Essa regra garante que criar objetos não energize ou movimente o braço.

### Leitura

```text
Joint.current_position()
  → servo.ReadPosSpeed(id)
  → validate_result(...)
  → posição bruta

Joint.current_angle()
  → current_position()
  → JointConfig.position_to_angle(...)

Joint.is_moving()
  → servo.ReadMoving(id)
  → validate_result(...)
  → booleano
```

Uma posição fora do intervalo calibrado pode ser lida como count, mas não pode
ser convertida em ângulo físico válido.

### Habilitação de torque

```text
ler posição atual
  → escrever a posição atual como alvo
  → habilitar torque no endereço 40
  → reler e confirmar o registrador
```

Preparar o alvo atual reduz o risco de o servo buscar um alvo antigo ao receber
torque. Isso não elimina a necessidade de apoiar o braço.

### Comando atual

No snapshot documentado, `Joint.command(angle, speed, acc)`:

1. escolhe os valores informados ou os padrões da configuração;
2. valida velocidade e aceleração;
3. converte e valida o ângulo;
4. chama `WritePosEx`;
5. valida a comunicação;
6. retorna os counts enviados como alvo.

O método não lê a posição nem consulta `ReadMoving`. A confirmação do SDK
significa que o comando foi recebido, não que a meta foi alcançada.

### Comparação de chegada

`Joint.position_error(target, current)` calcula o erro absoluto em counts.
`Joint.is_within_tolerance(target, current)` compara esse erro com
`config.tolerance_counts`:

```text
erro = abs(target_position - current_position)
chegou numericamente = erro <= tolerance_counts
```

As duas operações são puras: recebem posições já conhecidas e não acessam o
servo. Estar dentro da tolerância é uma condição necessária para concluir um
movimento, mas o futuro `move()` também observará o estado `moving`.

## Arquitetura planejada, ainda não implementada

### Movimento individual robusto

A leitura isolada `Joint.is_moving()` e o comando não bloqueante já estão
implementados. A continuação da Etapa 3 adicionará novamente `move()`:

```python
joint.command(angle)  # já implementado: envia e retorna imediatamente
joint.move(angle)     # envia e aguarda com timeout
```

`move()` deverá observar `ReadMoving`, tolerância e timeout, distinguindo
sucesso, servo parado fora do alvo e falha de comunicação.

### Múltiplas juntas

`RobotArm` manterá a coleção ordenada, validará poses completas e usará
`SyncWritePosEx`. SyncWrite sincroniza o início do pacote, não garante chegada
simultânea; trajetórias temporizadas são uma preocupação posterior.

### Fora do escopo atual

- cinemática direta e inversa;
- coordenadas cartesianas XYZ;
- Jacobiano e controle de velocidade cartesiana;
- dinâmica, torque calculado e compensação de gravidade;
- garra;
- persistência automática de calibração.
