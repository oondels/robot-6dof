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
| zero mecânico | pendente | posicionar na referência física escolhida |
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

## Estado atual

A ferramenta e seus testes estão concluídos. O operador realizou duas leituras
físicas, mas a relação delas com a posição mecânica ainda não foi confirmada. O
assistente não executou comandos no hardware.
