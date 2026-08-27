# Relatório de calibração dinâmica de load — servo ID 6

Data: 27 de agosto de 2026

## Objetivo

Avaliar a relação entre o load informado pelo servo e as condições dinâmicas
do comando executado pelo gatilho `L2` do controle PS5. Os ensaios foram feitos
sem objeto, com fechamento da junta, variando speed e aceleração.

O objetivo desta etapa é estabelecer a carga dinâmica normal antes de definir
limites de contato e fixação.

## Explicação direta do resultado

O load não indica somente que o servo encontrou um objeto. Ele também aumenta
quando o servo se movimenta rapidamente, mesmo sem nenhum objeto na garra.

Nos ensaios sem objeto foram observados os seguintes valores:

```text
L2 entre 0% e 25%   -> load normal médio de 61
L2 entre 50% e 75%  -> load normal médio de 149
L2 entre 75% e 100% -> load normal médio de 253
```

Isso acontece porque o trigger controla a velocidade com que a posição alvo é
alterada:

```text
Pressão baixa no L2
    -> alvo muda lentamente
    -> servo acompanha o alvo
    -> erro de posição pequeno
    -> load baixo
```

```text
Pressão alta no L2
    -> alvo muda rapidamente
    -> posição real fica atrás do alvo
    -> erro de posição aumenta
    -> servo aplica mais esforço
    -> load aumenta
```

O load observado pode ser entendido como a combinação de duas causas:

```text
load_total = load_causado_pelo_movimento + load_causado_pelo_objeto
```

O servo informa somente o valor total. Por isso, um valor como `120` pode
significar tanto contato com um objeto quanto apenas um fechamento rápido.

Os limites inicialmente considerados:

```text
load > 90   -> contato
load >= 120 -> objeto fixado
```

não funcionam isoladamente. Durante movimento livre e com pressão alta no L2,
o load chegou próximo de `280` sem objeto.

Uma estimativa provisória da carga normal causada pela velocidade é:

```text
load_normal_estimado = 36,31 + 4,10 * abs(velocidade_em_graus_por_segundo)
```

Exemplo com velocidade real de `20°/s`:

```text
load_normal_estimado = 36,31 + 4,10 * 20
load_normal_estimado = aproximadamente 118
```

Nesse movimento, um load de `120` é normal e não confirma contato.

Exemplo com velocidade real de `5°/s`:

```text
load_normal_estimado = 36,31 + 4,10 * 5
load_normal_estimado = aproximadamente 57
```

Nesse caso, um load de `120` representa aproximadamente `63` counts acima da
carga dinâmica esperada e pode indicar contato.

A variável relevante para a futura detecção é:

```text
load_excedente = load_medido - load_normal_estimado
```

Exemplo:

```text
load medido:          160
load normal estimado: 60
load excedente:       100
```

Esse excesso pode ter sido provocado pelo objeto. O limite final do excesso
ainda precisa ser determinado comparando ensaios equivalentes com e sem
objeto.

Em resumo, o controle não deve perguntar apenas:

> O load passou de 120?

Ele deve avaliar:

> O load está maior do que seria normal para esta velocidade, pressão do
> trigger e condição de movimento?

## Dados analisados

Foram encontrados nove arquivos CSV. Dois contêm somente o cabeçalho e foram
descartados. Os sete ensaios válidos totalizam `783` amostras, das quais `456`
representam movimento ativo antes do limite angular inferior.

Os nomes dos arquivos e o campo `label` permanecem como `speed700_acc30_l2`,
mas o conteúdo registra também as configurações `1400/30`, `1400/60`,
`3400/60` e `3400/120`. Este relatório usa `command_speed` e
`command_acceleration` do CSV como fonte da verdade.

Todas as medições válidas pertencem à junta `gripper`, servo ID `6`, usando
`L2` para reduzir o ângulo.

## Qualidade dos dados

### Condições bem registradas

- valor normalizado do trigger;
- `delta_time`;
- taxa angular solicitada;
- velocidade angular medida;
- speed e aceleração do comando;
- alvo, posição atual e erros;
- load bruto e decodificado;
- tensão, temperatura e corrente;
- estado de movimento;
- timestamp do sistema e do controlador.

### Limitações

- existe um primeiro ensaio com objeto para `speed=700`, `acc=30` e `L2`, mas
  ainda não há repetição nem pares com objeto para as demais configurações;
- não existem amostras com `R2` para comparar o sentido oposto;
- a pressão do trigger não foi mantida em patamares controlados durante cada
  sessão;
- os percursos e quantidades de amostras diferem entre os ensaios;
- a tensão permaneceu praticamente constante;
- a temperatura permaneceu praticamente constante;
- a corrente apresentou comportamento coerente no ensaio com objeto, mas sua
  escala ainda deve ser confirmada antes de uso como limite de segurança;
- os nomes dos arquivos não refletem todas as configurações internas.

Por essas limitações, os dados permitem caracterizar a carga dinâmica normal,
mas ainda não permitem definir uma equação final de contato.

## Condições elétricas e térmicas

Durante todos os ensaios:

```text
tensão:      9,3..9,4 V
temperatura: 32..34 °C
corrente:    0..0,026 A registrados
```

Não houve variação suficiente de tensão ou temperatura para calcular seus
efeitos sobre o load.

No ensaio sem objeto, a corrente ficou entre `0` e `0,026 A`. No novo ensaio
com objeto, ela subiu para `0,104..0,546 A` durante o contato e permaneceu em
`0,468..0,572 A` com o servo bloqueado pelo objeto. Esse comportamento é
internamente coerente com o aumento do esforço. A escala ainda deve ser
confirmada antes de transformar a corrente em limite operacional de segurança.

## Ensaio com objeto macio — speed 700 / acc 30 / L2

Arquivo analisado:
`servo_load_gripper_speed700_acc30_l2_20260827_122838.csv`.

O ensaio possui `70` amostras e duração de `2,559 s`. A garra começou livre,
fechou sobre o objeto macio e continuou recebendo comando até o servo emitir o
erro de overload.

### Separação do ensaio em fases

| Fase | Intervalo | Amostras | Load | Corrente | Velocidade medida | Interpretação |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Movimento livre | `0..0,575 s` | 17 | média `137`, pico `248` | média `0,013 A`, pico `0,026 A` | até `49,28°/s` | O load cresce por causa do movimento rápido |
| Contato e desaceleração | `0,611..0,826 s` | 7 | média `425`, faixa `296..500` | `0,104..0,546 A` | cai de aproximadamente `34°/s` para `2°/s` | O objeto começa a impedir o fechamento |
| Servo bloqueado no objeto | `0,862..2,559 s` | 46 | média `472`, faixa `464..476` | média `0,528 A` | próxima de `0°/s` | Esforço sustentado até o overload |

Durante o bloqueio, o alvo permaneceu em `0°`, mas a posição real ficou entre
aproximadamente `9,9°` e `10,2°`. O erro estável de cerca de `10°`, junto da
velocidade próxima de zero, confirma que o servo não estava apenas em
movimento: ele estava impedido mecanicamente pelo objeto.

### Quando os limites fixos foram cruzados

Os limites de `90` e `120` foram cruzados ainda no movimento livre:

| Limite | Tempo | Trigger | Velocidade | Erro angular | Situação |
| ---: | ---: | ---: | ---: | ---: | --- |
| `load > 90` | `0,180 s` | `0,53` | `7,3°/s` | `3,67°` | Garra ainda livre |
| `load >= 120` | `0,252 s` | `0,70` | `19,6°/s` | `5,26°` | Garra ainda livre |
| `load >= 240` | `0,575 s` | `1,00` | `49,3°/s` | `12,14°` | Garra ainda em movimento rápido |

Portanto, esta medição confirma que `90`, `120` e até `240` não distinguem
contato quando usados isoladamente.

### Sinais que distinguiram o contato

Aplicando o modelo provisório do movimento livre:

```text
load_normal_estimado = 36,31 + 4,10 * abs(velocidade_em_graus_por_segundo)
```

o load excedente permaneceu baixo durante a maior parte do fechamento livre.
Quando o alvo chegou a `0°` e o objeto passou a bloquear a garra, o excedente
saltou para aproximadamente `120` counts e, na amostra seguinte, para mais de
`220` counts. Durante o bloqueio, permaneceu acima de `400` counts.

O contato ficou caracterizado pela combinação simultânea de:

```text
load acima do esperado para a velocidade
+ velocidade caindo para zero
+ erro de posição persistente
+ corrente aumentando
```

A tensão também caiu de `9,3 V` no movimento livre para `9,0 V` no bloqueio.
A temperatura permaneceu em `33 °C`, pois o ensaio foi curto.

### Relação com o erro de overload

O maior load instantâneo foi `500`, durante a transição de contato. Depois
disso, o servo permaneceu por aproximadamente `1,7 s` com load perto de `470`
e corrente perto de `0,53 A`, antes do encerramento associado ao erro.

Isso indica que o overload não deve ser interpretado apenas como um único
valor instantâneo acima de `240`. Neste ensaio, o estado perigoso foi o esforço
alto e sustentado com velocidade praticamente zero.

Este resultado ainda não define sozinho os limites finais de contato, fixação
e segurança. Ele fornece uma primeira separação clara entre carga dinâmica e
bloqueio, mas precisa ser repetido para verificar a variação entre execuções e
entre tipos de objeto.

## Resultado por configuração

A tabela considera somente amostras em que o servo informou movimento e ainda
não estava parado no limite inferior.

| Speed | Acc | Amostras | Trigger médio | Load médio | Mediana | P95 | Pico | Erro angular médio | Erro máximo |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 700 | 30 | 77 | 0,950 | 232,2 | 272 | 284 | 288 | 11,77° | 14,23° |
| 1400 | 30 | 160 | 0,599 | 160,4 | 114 | 284 | 288 | 7,03° | 14,16° |
| 1400 | 60 | 84 | 0,619 | 163,3 | 138 | 280 | 284 | 5,72° | 10,73° |
| 3400 | 60 | 64 | 0,756 | 203,3 | 232 | 284 | 288 | 7,31° | 10,80° |
| 3400 | 120 | 71 | 0,760 | 209,8 | 256 | 284 | 284 | 6,47° | 9,08° |

Os valores não formam uma relação monotônica isolada entre speed, aceleração
e load porque a pressão média do trigger também mudou. Por exemplo, a
configuração `700/30` recebeu trigger médio de `0,950`, enquanto `1400/30`
recebeu `0,599`. A comparação direta entre suas médias seria incorreta.

## Relação com a pressão do trigger

Agrupando todas as amostras ativas por pressão do `L2`:

| Faixa do trigger | Amostras | Load médio | Mediana | P95 | Pico |
| --- | ---: | ---: | ---: | ---: | ---: |
| `0,00..<0,25` | 55 | 61,3 | 68 | 88 | 96 |
| `0,25..<0,50` | 117 | 110,0 | 108 | 144,4 | 276 |
| `0,50..<0,75` | 29 | 149,1 | 156 | 190 | 192 |
| `0,75..1,00` | 255 | 253,4 | 276 | 284 | 288 |

O load normal aumenta fortemente com a pressão do trigger, mesmo sem contato
com objeto.

Consequência direta:

```text
load > 90
load >= 120
```

não podem ser usados isoladamente como limites globais de contato ou fixação.
Em movimento livre, esses valores são normais a partir de pressões moderadas
do gatilho.

## Relação com velocidade e erro de seguimento

Nas amostras ativas, o load apresentou correlação forte com:

| Variável | Correlação linear com load |
| --- | ---: |
| pressão do trigger | `0,90` aproximado no conjunto |
| velocidade angular medida | até `0,99` por configuração |
| erro angular | entre `0,98` e `1,00` por configuração |

O comportamento observado é:

```text
mais pressão no trigger
    -> alvo muda mais rapidamente
    -> posição real fica atrás do alvo
    -> erro de seguimento aumenta
    -> controlador interno aplica mais esforço
    -> load aumenta
```

Portanto, parte significativa do load observado é carga dinâmica de
acompanhamento, não contato mecânico.

## Modelos empíricos provisórios

Foram ajustadas regressões lineares simples às `456` amostras ativas. Elas
descrevem somente esta montagem, este sentido, esta faixa elétrica e esta
sessão.

### Pela pressão do trigger

```text
load_estimado = 20,18 + 234,90 * trigger
R² = 0,809
erro médio do modelo = 38,39 counts de load
```

### Pelo erro angular

```text
load_estimado = 53,04 + 17,73 * erro_angular_em_graus
R² = 0,869
erro médio do modelo = 31,79 counts de load
```

### Pela velocidade angular medida

```text
load_estimado = 36,31 + 4,10 * abs(velocidade_em_graus_por_segundo)
R² = 0,975
erro médio do modelo = 13,89 counts de load
```

O modelo por velocidade foi o que melhor descreveu estes dados, mas não deve
ser colocado no controle ainda. As variáveis evoluem juntas durante o mesmo
fechamento e ainda não houve validação com objeto.

## Interpretação para o controle

Um detector robusto não deve comparar apenas:

```text
load_atual >= limite_fixo
```

A hipótese sustentada pelos dados é comparar o load medido com a carga dinâmica
esperada para o movimento atual:

```text
load_excedente = load_medido - load_dinamico_estimado
```

O contato seria indicado por um `load_excedente` positivo e sustentado,
acompanhado de aumento do erro de posição ou queda de velocidade em relação ao
comando.

Essa hipótese precisa ser validada com ensaios pareados:

```text
mesma configuração + mesmo trigger + mesmo percurso
sem objeto vs com objeto
```

## Conclusões

1. O load em movimento livre depende fortemente da pressão do trigger.
2. A pressão altera a taxa do alvo e, consequentemente, o erro de seguimento.
3. A velocidade angular medida foi a variável que melhor explicou o load nesta
   sessão.
4. Speed e aceleração não podem ser analisados isoladamente enquanto trigger e
   percurso variarem entre ensaios.
5. Os limites fixos `90/120` gerariam falsos positivos em movimento livre.
6. A tensão e a temperatura permaneceram estáveis; seus efeitos não foram
   medidos.
7. A leitura de corrente respondeu de forma coerente ao contato e ao bloqueio,
   mas sua escala precisa ser validada antes de virar limite de segurança.
8. O ensaio com objeto confirmou que o detector deve considerar load
   excedente, erro de posição e
   velocidade, não apenas load absoluto.
9. No ensaio com objeto, o estado anterior ao overload apresentou load
   sustentado próximo de `470`, corrente próxima de `0,53 A` e velocidade
   próxima de zero por aproximadamente `1,7 s`.

## Ensaios necessários para fechar o modelo operacional

- repetir cada combinação com trigger mantido em `0,25`, `0,50`, `0,75` e
  `1,00`;
- realizar um ensaio sem objeto e outro com objeto para cada patamar;
- repetir no mínimo três vezes cada condição;
- testar `L2` e `R2` separadamente;
- variar tensão de forma controlada e registrar a tensão real;
- repetir com servo frio e aquecido;
- validar a leitura de corrente com instrumento externo ou documentação
  específica do modelo;
- corrigir label e nome do arquivo para refletirem speed, aceleração e trigger
  efetivamente usados.

## Estado da decisão

A calibração dinâmica sem objeto está caracterizada e o primeiro ensaio com
objeto confirmou que o load excedente separa melhor o contato do que um limite
absoluto. O limite final de contato/fixação ainda não está fechado porque há
somente uma execução com objeto. A próxima etapa deve repetir o mesmo ensaio e
produzir pares controlados com e sem objeto.
