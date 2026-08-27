# Calibração de load dos servos

Este documento descreve como medir, interpretar e utilizar o `load` dos
servos Feetech/SCServo do robô. O procedimento é definido por servo e por
aplicação mecânica. Um valor obtido em uma junta não deve ser copiado para
outra junta sem uma nova medição.

## Servo Feetech STS3215 usado no robô

O robô utiliza servos Feetech `STS3215`. Os resultados deste documento são
medições do conjunto real formado por servo, alimentação, montagem mecânica e
software de controle. Eles não são uma especificação universal de todos os
STS3215.

O ensaio mais recente da garra utilizou:

```text
modelo:       Feetech STS3215
servo ID:     6
speed:        700
aceleração:   30
controle:     gatilho L2
tensão livre: 9,3 V
objeto:       macio
```

## O que o load representa

Nos servos SMS/STS, o load atual é lido no registrador `PRESENT_LOAD`, endereço
`60`, com dois bytes. O valor indica o esforço de saída aplicado pelo servo,
em uma escala de `0` a `1000`:

```text
0    = 0%
500  = 50%
1000 = 100%
```

O load não é uma medição calibrada de força ou torque. Ele não informa
diretamente newtons, newton-metro ou quilogramas. A leitura é útil como sinal
relativo para comparar o comportamento do mesmo servo sob as mesmas condições
de montagem, tensão, velocidade, aceleração e temperatura.

O bit `10` registra a direção do esforço. A magnitude precisa ser separada do
valor bruto antes de qualquer comparação:

```python
LOAD_DIRECTION_BIT = 1 << 10
LOAD_MAGNITUDE_MASK = LOAD_DIRECTION_BIT - 1

magnitude = raw_load & LOAD_MAGNITUDE_MASK
direction = "negativa" if raw_load & LOAD_DIRECTION_BIT else "positiva"
load_percent = magnitude / 10.0
```

Comparar diretamente o valor bruto pode produzir uma falsa sobrecarga quando
o bit de direção estiver ativo.

## Load não substitui calibração mecânica

Antes de calibrar load, o servo precisa ter posição, zero, direção e limites
seguros corretamente configurados. Um limite angular contra um batente físico
faz o load subir mesmo sem carga externa e contamina toda a medição.

As referências devem permanecer separadas:

```text
batente físico
    !=
limite operacional seguro
    !=
zero de referência
```

O limite operacional deve manter margem antes do batente. A validação deve ser
feita primeiro por posição e erro de acompanhamento; somente depois o load é
usado para detectar contato ou esforço externo.

## Grandezas que devem ser registradas

Uma amostra de calibração deve conter, no mínimo:

| Campo | Finalidade |
| --- | --- |
| tempo | identificar duração da carga e eventos transitórios |
| servo e ensaio | associar a medição ao hardware e à condição física |
| operação | distinguir movimento, repouso e sentido do comando |
| posição alvo | saber o que foi solicitado ao servo |
| posição atual | saber o que a mecânica realmente executou |
| erro de posição | detectar bloqueio ou resistência mecânica |
| load bruto | preservar o valor recebido do hardware |
| magnitude e direção | permitir comparação correta |
| velocidade e aceleração | tornar ensaios diferentes comparáveis |
| tensão e temperatura | contextualizar mudanças de comportamento |

O erro de posição é calculado por:

```text
erro = valor absoluto(posição alvo - posição atual)
```

Load crescente acompanhado por erro crescente indica que o servo continua
aplicando esforço, mas a mecânica deixou de acompanhar o alvo.

## Procedimento de calibração

### 1. Preparação

- Apoiar o robô para que nenhuma junta dependa do torque para não cair.
- Manter acesso imediato ao corte de alimentação.
- Encerrar qualquer processo que esteja usando a porta serial.
- Garantir que o programa de medição seja o único dono da serial.
- Conferir zero, direção e limites seguros do servo.
- Usar inicialmente um objeto macio ou uma resistência controlada.
- Nunca começar pelo batente, por um objeto rígido ou pelo hardware em carga
  máxima.

### 2. Medição sem carga externa

Percorrer a faixa operacional em pequenos passos e registrar o load em cada
posição. Repetir o percurso mais de uma vez.

O objetivo é descobrir:

- ruído normal da leitura;
- picos causados por aceleração;
- carga sustentada em repouso;
- regiões de atrito ou interferência mecânica;
- maior load observado sem carga externa;
- erro normal entre alvo e posição atual.

Se o load subir de forma sustentada perto de um limite sem carga externa, a
calibração mecânica deve ser corrigida antes de continuar.

### 3. Medição com carga controlada

Repetir o mesmo movimento, velocidade e aceleração com uma resistência macia
ou controlada. Aproximar em passos pequenos e interromper antes da proteção do
servo.

Registrar quatro regiões:

```text
operação livre
    -> início do contato
    -> esforço suficiente para a operação
    -> região insegura / proteção do servo
```

O valor de contato deve ficar acima dos picos normais. O valor operacional
deve confirmar que a carga está segura sem se aproximar da região de proteção.

### 4. Repetição

Um limite não deve ser definido por uma única execução. Repetir os ensaios
considerando:

- servo frio e aquecido;
- diferentes posições da junta;
- variações normais da fonte;
- diferentes objetos ou cargas previstas;
- abertura e fechamento;
- pelo menos três sessões controladas por condição.

Usar valores sustentados e distribuições, não somente o maior pico.

## Definição dos limites operacionais

Cada servo pode precisar de limites diferentes. Uma calibração completa pode
definir:

| Limite | Comportamento esperado |
| --- | --- |
| normal | movimento sem resistência externa relevante |
| aviso | indício de contato ou aumento anormal de esforço |
| operação | esforço suficiente para cumprir a função da junta |
| segurança | interromper aumento de esforço antes da proteção interna |

Um aviso pode reagir ao primeiro cruzamento. Uma decisão que altera movimento
deve preferencialmente exigir leituras consecutivas ou outra forma de filtro
para rejeitar picos transitórios.

Os limites devem ser registrados junto com:

- identificação e modelo do servo;
- função mecânica e montagem;
- data da calibração;
- zero e limites angulares usados;
- velocidade e aceleração;
- tensão de alimentação;
- condição de carga;
- arquivos CSV que sustentam a decisão.

## Uso durante a operação

A leitura de load deve ser interpretada no contexto do comando atual:

- durante movimento livre, serve como telemetria e detecção de anomalia;
- durante aproximação, pode indicar primeiro contato;
- durante fixação, pode confirmar que a carga foi alcançada;
- durante abertura ou alívio, não deve ser confundida com contato no sentido
  oposto;
- perto da proteção, novos comandos que aumentem o esforço devem ser
  interrompidos.

Parar de incrementar um alvo não é necessariamente o mesmo que remover o
esforço. Se a posição atual estiver distante do alvo, o controlador interno do
servo continuará tentando corrigir o erro. A estratégia operacional deve
decidir conscientemente entre manter força, aliviar o alvo, desabilitar torque
ou executar uma retirada segura.

## Sobrecarga e tratamento de falhas

O servo pode responder com:

```text
[ServoStatus] Overload error!
```

Esse erro vem do status do hardware. Ele pode continuar aparecendo em comandos
seguintes, inclusive durante uma tentativa de desabilitar torque. Uma exceção
durante o desligamento não confirma se o torque permaneceu habilitado ou foi
desabilitado; significa que o software não conseguiu confirmar o resultado.

Ao observar sobrecarga:

1. não enviar novos comandos que aumentem o esforço;
2. acionar o procedimento de segurança previsto para a junta;
3. cortar a alimentação se o estado do torque não puder ser confirmado;
4. remover a causa somente quando for fisicamente seguro;
5. registrar alvo, posição, load, tempo, tensão, temperatura e mensagem de
   erro;
6. não repetir o ensaio na mesma região sem revisar os limites.

O valor imediatamente anterior ao erro não deve ser adotado como limite de
operação. A proteção pode depender tanto da magnitude quanto do tempo de
permanência.

## Estudo de caso: Feetech STS3215, servo ID 6

Este estudo registra sessões específicas do servo ID `6`. Os números abaixo
não são limites globais do robô.

### Efeito da calibração mecânica

Antes da correção do zero mecânico, o servo sem objeto terminou o fechamento
com load médio de `136`, pico de `140` e erro angular de aproximadamente
`2,76°`. O servo estava aplicando esforço contra o próprio mecanismo.

Após atualizar a referência e manter o limite antes do batente, um ensaio
lento sem objeto apresentou load médio final de `57,2`, pico final de `72`,
pico geral de `84` e erro angular final de `0,97°`.

### Efeito do trigger e da velocidade

Nos ensaios dinâmicos sem objeto, o load aumentou junto com a pressão no `L2`:

| Faixa do L2 | Load médio sem objeto |
| --- | ---: |
| `0..25%` | `61` |
| `50..75%` | `149` |
| `75..100%` | `253` |

Com `speed=700`, `acc=30` e L2 pressionado rapidamente, o load chegou a `248`
enquanto a garra ainda estava livre. Portanto, os antigos valores absolutos
`90` para contato e `120` para fixação geram falsos positivos e não devem ser
usados isoladamente.

Nas amostras livres, a velocidade medida explicou melhor o load do que um
limite fixo. O modelo empírico provisório foi:

```text
load esperado pelo movimento = 36,31 + 4,10 * abs(velocidade em graus/s)
load excedente = load medido - load esperado pelo movimento
```

Esse modelo descreve a montagem e as sessões medidas. Ele não converte load
em força ou torque e deve ser recalibrado quando houver mudança relevante.

### Ensaio com objeto macio até o overload

O arquivo
`servo_load_gripper_speed700_acc30_l2_20260827_122838.csv` registrou `70`
amostras durante `2,559 s`:

| Fase | Load | Corrente | Velocidade medida |
| --- | ---: | ---: | ---: |
| movimento livre | média `137`, pico `248` | média `0,013 A` | até `49,28°/s` |
| contato e desaceleração | `296..500` | `0,104..0,546 A` | caiu em direção a zero |
| bloqueio no objeto | média `472` | média `0,528 A` | próxima de `0°/s` |

No bloqueio, o alvo permaneceu em `0°`, a posição real ficou próxima de `10°`
e a tensão caiu de `9,3 V` para `9,0 V`. O servo permaneceu aproximadamente
`1,7 s` com load perto de `470`, corrente perto de `0,53 A` e velocidade quase
zero antes do encerramento associado ao `Overload error`.

O estado perigoso observado foi esforço alto e sustentado com o servo
bloqueado. Não foi apenas um pico instantâneo acima de `240`.

### Critério provisório implementado

A função `validate_load`, em `src/utils/validate_load.py`, considera contato ou
bloqueio somente quando todos estes sinais aparecem na mesma amostra:

```text
load excedente >= 100
velocidade absoluta <= 5 graus/s
erro angular absoluto >= 5 graus
corrente absoluta >= 0,10 A
```

Exemplo de uso:

```python
from src.utils.validate_load import validate_load

contact_detected = validate_load(
    raw_load=joint.current_load(),
    measured_velocity_deg_s=measured_velocity,
    angle_error_deg=target_angle - current_angle,
    current_a=joint.current_current(),
)
```

A função avalia apenas uma amostra. Para uso no controle real, a decisão deve
exigir leituras consecutivas e possuir uma ação segura definida. Os limites
ainda são provisórios porque existe somente uma execução dinâmica com objeto.

## Ferramenta existente

O projeto possui atualmente:

```bash
python -m src.calibration.measure_gripper_load --label <nome_do_ensaio>
```

Ela executa passos supervisionados de `1°`, coleta dez amostras por passo e
salva o CSV em `/tmp` por padrão. O código atual seleciona especificamente a
junta chamada `gripper`; portanto, a metodologia deste documento é geral para
servos, mas a ferramenta ainda não é uma interface genérica para qualquer ID.

Durante uma evolução futura, a ferramenta pode receber explicitamente o servo
ou a junta a medir. Essa mudança deve manter validação de limites, propriedade
exclusiva da serial, confirmação de torque e encerramento seguro.

## Critério de conclusão

A calibração de load de um servo está concluída quando:

- a calibração mecânica não produz carga artificial nos limites;
- os ensaios sem carga são repetíveis;
- contato e operação estão claramente separados do ruído normal;
- existe margem suficiente antes da proteção do servo;
- direção, magnitude e erro de posição são considerados;
- os limites estão associados ao servo e à montagem corretos;
- os dados brutos e a justificativa da decisão foram preservados;
- a estratégia de falha foi validada primeiro sem hardware real, depois com
  teste controlado.
