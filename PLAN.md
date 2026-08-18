# Plano de aprendizagem: braço robótico com múltiplas juntas

## Objetivo

Construir, de forma gradual e didática, uma base robusta para controlar um
braço robótico de seis graus de liberdade. Primeiro será consolidado o controle
de uma junta; depois, a mesma abstração será usada para controlar até seis
juntas sem duplicação de lógica.

A primeira versão trabalha somente no espaço das juntas, usando ângulos físicos
em graus. Garra, cinemática direta, cinemática inversa e planejamento temporal
de trajetórias ficam para versões posteriores.

## Método de trabalho

- Apenas uma tarefa será trabalhada por vez.
- Antes de cada alteração serão explicados os conceitos de Python, orientação a
  objetos e robótica envolvidos.
- O código necessário será enviado no chat para ser digitado e aplicado pelo
  estudante.
- Depois da aplicação, o código será relido e verificado antes de avançar.
- `TASKS.md` será atualizado somente depois que os critérios da etapa forem
  atendidos.
- Toda decisão, mudança aplicada ou evolução validada deve atualizar, no mesmo
  ciclo, a documentação afetada. Uma mudança não é considerada concluída se o
  código e a documentação estiverem divergentes.
- Testes automatizados não devem depender de hardware conectado.
- Movimentos reais serão executados pelo estudante, com o braço apoiado, área
  livre e velocidade e aceleração reduzidas.

## Arquitetura planejada

### `JointConfig`

Representará a configuração imutável de uma junta:

- nome e ID do servo;
- posição bruta correspondente ao zero mecânico;
- direção positiva, representada por `1` ou `-1`;
- limites angulares mínimo e máximo;
- velocidade, aceleração e tolerância padrão.

Uma configuração será rejeitada antes de qualquer acesso ao barramento quando
for inconsistente ou produzir posições fora de `0..4095`.

### `Joint`

Será responsável somente por uma junta:

- validar e converter graus físicos em counts do servo;
- ler posição e estado de movimento;
- produzir uma fotografia imutável do alvo e do estado observado;
- habilitar e desabilitar torque;
- enviar um alvo sem bloquear;
- mover e aguardar a chegada com tolerância e timeout;
- relatar falhas de comunicação ou uma parada fora do alvo.

A conexão serial continuará fora de `Joint`. Todas as juntas compartilharão o
mesmo objeto `sms_sts` e o mesmo barramento.

### `RobotArm`

Será responsável pelo conjunto ordenado de juntas:

- rejeitar nomes e IDs duplicados;
- controlar o torque do conjunto;
- ler os ângulos atuais;
- validar poses completas informadas como mapa por nome;
- enviar os alvos em um pacote com `SyncWritePosEx`;
- aguardar todas as juntas e identificar qual delas falhou.

API pretendida:

```python
arm.move_pose(
    {
        "base": 0.0,
        "shoulder": 25.0,
    },
    timeout=5.0,
)
```

Uma pose sincronizada deverá conter exatamente todas as juntas configuradas.
Movimentos isolados continuarão sendo feitos pela própria `Joint`.

## Modelo angular

A interface pública usará graus físicos. A conversão planejada é:

```text
posição = zero_position + direction * angle * 4096 / 360
```

Cada comando será verificado contra os limites angulares da junta e contra o
intervalo bruto do servo. Nesta primeira versão não serão aceitos intervalos
que atravessem a transição do encoder entre `4095` e `0`.

## Movimento e falhas

- Todos os alvos de uma pose serão validados antes da primeira escrita.
- `SyncWritePosEx` sincroniza o início dos comandos, mas não garante que as
  juntas cheguem ao destino ao mesmo tempo.
- A espera consultará periodicamente posição e estado de movimento.
- Cada consulta será representada por `MovementStatus`, contendo alvo, posição,
  erro, estado de movimento e resultado da comparação com a tolerância.
- Um servo parado fora da tolerância ou um timeout abortará a operação.
- A chegada à tolerância concluirá a espera e retornará o último
  `MovementStatus`, mesmo se a leitura consecutiva de `moving` ainda for
  verdadeira.
- O diagnóstico indicará junta, alvo, posição medida e erro.
- O torque permanecerá habilitado após falhas para reduzir o risco de uma junta
  sustentada pela gravidade cair. O desligamento será sempre explícito.

## Calibração segura

A calibração será realizada uma junta por vez e não buscará batentes de forma
automática:

Uma ferramenta separada de `Joint` lerá counts brutos antes de existir uma
configuração física confiável. Ela não alterará torque nem enviará movimento;
cada leitura dependerá de uma ação explícita do operador e a porta será fechada
em falhas.

1. Apoiar mecanicamente o braço e desabilitar o torque.
2. Posicionar manualmente a junta no zero físico e registrar os counts.
3. Fazer um pequeno deslocamento no sentido físico positivo para descobrir a
   direção do encoder.
4. Medir limites seguros com margem antes dos batentes mecânicos.
5. Registrar zero, direção e limites no arquivo de configuração.
6. Validar pequenos deslocamentos com velocidade e aceleração reduzidas.

A junta atual usa o ID `6`. IDs e calibrações das próximas juntas não serão
presumidos.

## Estratégia de testes

Será usado `unittest`, disponível na biblioteca padrão do Python, junto com um
servo falso. Os testes cobrirão:

- configurações válidas e inválidas;
- conversão angular normal e invertida;
- limites de ângulo, posição, velocidade e aceleração;
- habilitação e desabilitação de torque;
- chegada ao alvo, parada fora da tolerância e timeout;
- nomes e IDs duplicados;
- poses incompletas ou com juntas desconhecidas;
- falhas ao montar ou transmitir um pacote sincronizado;
- limpeza do buffer de SyncWrite após sucesso e erro.

## Critérios finais

- Cada junta possui zero, direção e limites físicos próprios.
- Configurações e poses inválidas falham antes de escrever no barramento.
- Movimentos individuais possuem timeout e diagnóstico.
- Poses completas são transmitidas em um único pacote.
- A lógica pode ser verificada sem hardware.
- A estrutura cresce de duas para seis juntas sem duplicar controle.
- Cinemática, garra e trajetórias temporizadas permanecem fora da primeira
  versão.
