# Calibração manual da primeira junta

Este documento orienta a medição da junta de servo ID `6`. A calibração é
manual: o software apenas lê counts e nunca procura batentes automaticamente.

## O que a ferramenta garante

`calibration.read_joint_position`:

- valida o ID antes de abrir a porta;
- lê a posição bruta com `ReadPosSpeed` somente quando o operador pressiona
  Enter;
- valida erros de comunicação e de pacote;
- fecha a porta mesmo quando ocorre uma exceção;
- não habilita ou desabilita torque;
- não chama `WritePosEx` nem envia alvo de movimento.

Ela não consegue garantir que o torque já esteja desligado, que o braço esteja
apoiado ou que a montagem esteja livre. Essas condições dependem do operador.
O programa não desabilita torque automaticamente porque soltar uma junta sob
carga também pode causar queda.

## Checklist antes de conectar

Não execute a ferramenta enquanto algum item estiver pendente:

- [ ] O braço está desligado e apoiado, sem depender do torque para sustentar
  seu peso.
- [ ] A junta ID `6` foi identificada fisicamente.
- [ ] Cabos, polaridade, tensão da fonte e aterramento foram conferidos.
- [ ] A área completa de movimento está livre de pessoas e objetos.
- [ ] Existe acesso imediato ao corte de alimentação.
- [ ] A junta pode ser movimentada manualmente sem atingir um batente.
- [ ] O operador sabe que resistência inesperada significa **parar**, não
  aplicar mais força.

## Executar a leitura

Somente o operador diante do braço deve executar:

```bash
python -m calibration.read_joint_position \
    --servo-id 6 \
    --port /dev/ttyUSB0 \
    --baudrate 1000000
```

Controles:

- `Enter`: realiza exatamente uma leitura;
- `q` + `Enter`: fecha a ferramenta;
- `Ctrl+C`: encerra e fecha a porta.

Se a junta resistir ao movimento manual, interrompa o procedimento e corte a
alimentação. Não force a junta. A ferramenta não altera o estado do torque.

## Medições que serão feitas

Os valores abaixo só serão preenchidos após observação física:

| Medição | Counts | Como será determinada |
| --- | ---: | --- |
| zero mecânico | **2045** | mediana de dez leituras na referência física |
| pequeno deslocamento positivo | pendente | mover manualmente no sentido positivo |
| limite mínimo seguro | pendente | aproximar manualmente, mantendo margem |
| limite máximo seguro | pendente | aproximar manualmente, mantendo margem |

A direção será `1` se um deslocamento angular positivo aumentar os counts e
`-1` se diminuir. Os limites registrados serão seguros, com margem antes dos
batentes; não serão os batentes físicos máximos.

Os valores `2048`, `-90°` e `90°` usados nos testes são apenas exemplos e não
podem ser copiados como calibração real.

## Registro da primeira sessão física

Foram recebidas duas leituras válidas do servo ID `6`:

| Ordem | Posição lida | Posição física associada |
| --- | ---: | --- |
| 1 | 293 counts | aguardando confirmação do operador |
| 2 | 3250 counts | aguardando confirmação do operador |

Esses valores ainda não definem `zero_position`. É necessário confirmar se a
junta foi movida entre as leituras e qual delas corresponde à referência física
de `0°`. Se a junta não foi movida, a diferença deve ser investigada antes de
qualquer calibração ou comando.

## Registro da sessão de zero mecânico

Com a junta posicionada na referência física escolhida, o operador informou:

```text
2046, 2046, 2046, 2046, 2041,
2045, 2045, 2045, 2045, 2045
```

A mediana é `2045 counts`, adotada como `zero_position` medido. A faixa total
foi `2041..2046`, equivalente a cinco counts, aproximadamente `0,44°`. O valor
isolado `2041` não desloca a mediana. As leituras anteriores `293` e `3250` não
serão usadas na configuração porque suas posições físicas não foram associadas
ao zero.

## Registro da sessão de limites seguros

Com a junta posicionada nos limites operacionais, o operador informou:

- **Zero e limite inferior**: referência de fechamento em `2041 counts` com margem de repouso (`min_angle = -1.0°`).
- **Sentido positivo**: a abertura aumenta os counts (`direction = 1`).
- **Batente físico máximo observado**: $\approx 3545\text{ counts}$.
- **Limite superior seguro escolhido**: `3310 counts` (com margem de ~235 counts antes do batente).
- **Faixa angular calibrada**: `[-1.0°, 110.0°]`.

O histórico completo de medições e decisões está detalhado em [`docs/CALIBRATION_LOG.md`](CALIBRATION_LOG.md).

## Estado atual

A primeira junta (`gripper`, ID `6`) está com configuração calibrada e registrada em `robot_config.py`. Os testes sem hardware continuam passando.

