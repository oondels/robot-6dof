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

- não existe ainda um ensaio equivalente com objeto para cada configuração;
- não existem amostras com `R2` para comparar o sentido oposto;
- a pressão do trigger não foi mantida em patamares controlados durante cada
  sessão;
- os percursos e quantidades de amostras diferem entre os ensaios;
- a tensão permaneceu praticamente constante;
- a temperatura permaneceu praticamente constante;
- a corrente registrada é incompativelmente baixa para o esforço observado e
  precisa ser validada antes de uso operacional;
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

A corrente máxima de `0,026 A` não é coerente com um servo em movimento sob
load elevado. Antes de relacionar corrente e load, deve-se confirmar o
registrador, a escala e o comportamento específico do firmware do servo.

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
7. A leitura de corrente precisa ser validada antes de entrar em qualquer
   cálculo.
8. O próximo detector deve considerar load excedente, erro de posição e
   velocidade, não apenas load absoluto.

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

A calibração dinâmica sem objeto está caracterizada, mas o limite final de
contato/fixação ainda não está fechado. A próxima etapa deve produzir ensaios
pareados com objeto para calcular a margem entre load dinâmico esperado e load
de contato.
