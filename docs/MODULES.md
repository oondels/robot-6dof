# Referência dos módulos

Este documento descreve o código próprio do projeto no estado atual. Conteúdo
de `external/` é de terceiros e não é tratado como módulo da aplicação.

## Entrada e configuração

### `calibration/read_joint_position.py`

Ferramenta interativa para a calibração anterior a `JointConfig`.

| Função | Responsabilidade |
| --- | --- |
| `validate_servo_id()` | aceita somente IDs individuais `0..253` |
| `read_position()` | chama `ReadPosSpeed` e retorna counts validados |
| `run_reader()` | lê uma vez por Enter e encerra com `q` |
| `main()` | abre SDK/porta e garante fechamento com `finally` |

Os argumentos padrão são servo ID `6`, `/dev/ttyUSB0` e `1_000_000` baud. O
módulo não escreve registradores, não altera torque e não envia movimento.

### `main.py`

Responsabilidade: montar os objetos e gerenciar o ciclo de vida da porta.

Símbolos principais:

- `PORT`: porta serial, atualmente `/dev/ttyUSB0`;
- `BAUDRATE`: comunicação a `1_000_000` baud;
- `create_joints(servo)`: cria uma `Joint` para cada item de `JOINT_CONFIGS`;
- `main()`: verifica calibração, abre a porta, cria juntas, lê estados e fecha a
  porta em `finally`.

Não contém calibração nem regra de conversão. Não deve ser usado enquanto
`JOINT_CONFIGS` estiver vazio.

### `robot_config.py`

Responsabilidade: ser a fonte explícita das configurações físicas aprovadas.

API:

```python
JOINT_CONFIGS: tuple[JointConfig, ...]
```

Atualmente a tupla está vazia. Isso é uma trava de segurança, não uma falta de
valor padrão. Uma configuração só deve ser adicionada após calibração física.

## Modelo e controle

### `models/joint_config.py`

Contém constantes do servo e a dataclass imutável `JointConfig`.

Campos públicos:

| Campo | Unidade/significado |
| --- | --- |
| `name` | nome humano da junta |
| `servo_id` | ID individual no barramento |
| `zero_position` | count correspondente a `0°` físico |
| `direction` | `1` ou `-1` |
| `min_angle` | limite físico mínimo em graus |
| `max_angle` | limite físico máximo em graus |
| `speed` | velocidade padrão do SDK |
| `acc` | aceleração padrão do SDK |
| `tolerance_deg` | tolerância angular em graus |

Propriedade derivada:

- `tolerance_counts`: converte `tolerance_deg` para a resolução do encoder e
  garante o mínimo de um count.

Métodos públicos:

- `angle_to_position(angle) -> int`: valida o limite e converte graus em counts;
- `position_to_angle(position) -> float`: valida o intervalo calibrado e
  converte counts em graus;
- `validate_speed(speed)`: valida velocidade padrão ou override de comando;
- `validate_acceleration(acc)`: valida aceleração padrão ou override.

`frozen=True` impede alteração após construção. `slots=True` impede atributos
acidentais e reduz o estado do objeto ao contrato declarado.

### `models/Joint.py`

Contém `Joint`, o adaptador operacional de uma junta, e `MovementStatus`, o
registro imutável de uma observação do movimento.

`MovementStatus` possui os campos `target_position`, `current_position`,
`position_error`, `moving` e `within_tolerance`. Como usa `frozen=True` e
`slots=True`, seus valores não podem ser alterados nem ampliados com atributos
acidentais depois da criação.

Construção:

```python
Joint(servo=servo, config=config)
```

Propriedades delegadas:

- `name`, `servo_id`, `speed`, `acc` leem diretamente de `config`;
- `servo` é o objeto real ou falso que implementa os métodos esperados;
- `config` é a configuração imutável.

Métodos públicos atuais:

| Método | Efeito |
| --- | --- |
| `current_position()` | lê e retorna counts |
| `current_angle()` | lê e retorna graus físicos |
| `is_moving()` | consulta `ReadMoving` e retorna booleano |
| `enable_torque()` | prepara alvo atual, habilita e confirma torque |
| `disable_torque()` | desabilita e confirma torque |
| `is_torque_enabled()` | consulta o registrador de torque |
| `angle_to_position()` | delega a `JointConfig` |
| `position_to_angle()` | delega a `JointConfig` |
| `position_error()` | calcula erro absoluto entre alvo e posição atual |
| `is_within_tolerance()` | compara o erro com `config.tolerance_counts` |
| `movement_status()` | lê posição e movimento e retorna `MovementStatus` |
| `command()` | envia o alvo e retorna os counts, sem aguardar |
| `move()` | envia o alvo e aguarda tolerância, parada ou timeout |

Método interno:

- `_write_torque(value)`: encapsula escrita e validação do registrador 40.
- `_validate_wait_parameter(name, value)`: rejeita tempo não numérico, não
  finito ou não positivo antes de qualquer comando.

Dependências esperadas do objeto `servo`:

```text
ReadPosSpeed
ReadMoving
WritePosEx
write1ByteTxRx
read1ByteTxRx
getTxRxResult
getRxPacketError
```

`is_moving()` valida os dois canais de erro antes de converter o valor numérico
de `ReadMoving` em `bool`.

### `models/__init__.py`

Marcador de pacote. Não expõe uma API agregada.

## Utilitários

### `utils/validation.py`

Função pública:

```python
validate_result(servo, result, error, operation)
```

Lança `RuntimeError` com a descrição do SDK quando há falha de comunicação ou
erro de pacote. Não retorna valor no caminho de sucesso.

### `utils/__init__.py`

Marcador de pacote, sem API própria.

## Testes

### `tests/fake_servo.py`

Implementa um test double do SDK. Armazena registradores, registra comandos de
posição e devolve códigos compatíveis com `validate_result`.

Recursos:

- `position`, `speed` e `moving`: estado atual;
- `position_commands`: histórico de `WritePosEx`;
- `registers`: registradores simulados;
- `position_sequence` e `moving_sequence`: estados futuros;
- `queue_motion(...)`: agenda leituras sucessivas para simular movimento;
- `ReadMoving(...)`: permite testar espera e detecção de parada.

`WritePosEx` não altera automaticamente `position`. O teste deve enfileirar a
evolução desejada explicitamente.

### `tests/test_joint_config.py`

Testa imutabilidade, normalização, limites, direção, finitude, velocidade,
aceleração, conversões e erro de quantização.

Os valores `zero_position=2048` e limites `-90°..90°` são fixtures de teste.
Eles não descrevem o hardware real.

### `tests/test_joint.py`

Testa construção, propriedades delegadas, leitura, conversão, direção
invertida, torque, estado de movimento, comando não bloqueante, erro de posição
e limite de tolerância. Também testa a fotografia do movimento, inclusive o
caso em que o servo está parado fora da tolerância. A espera bloqueante cobre
sucesso, parada, timeout, validação anterior ao comando, comunicação e
preservação de torque.

### `tests/test_fake_servo.py`

Testa consumo das sequências e permanência no último estado depois que uma fila
simulada termina.

### `tests/test_read_joint_position.py`

Testa leitura bruta sem escritas, ID inválido, erro de comunicação, interação
por Enter e fechamento da porta quando a rotina falha.

### `tests/__init__.py`

Permite importar utilitários de teste como `tests.fake_servo`.

## Documentação e acompanhamento

### `README.md`

Entrada rápida, estado atual, estrutura e índice da documentação.

### `PLAN.md`

Arquitetura pretendida e decisões de evolução. Pode descrever recursos ainda
não implementados; sempre compare com `TASKS.md` e os testes.

### `TASKS.md`

Fonte do progresso incremental. A etapa atual é movimento individual robusto.

### `docs/ARCHITECTURE.md`

Fronteiras, fluxos, fórmula angular e arquitetura futura.

### `docs/SAFETY_AND_TESTING.md`

Regras para hardware, calibração, testes e diagnóstico.

## Arquivos auxiliares

### `requirements.txt`

Snapshot amplo do ambiente Python. Inclui SDK do servo e ferramentas não
essenciais ao núcleo, além de uma dependência Git via SSH. Ainda não é um
manifesto mínimo do projeto.

### `regras-operacao.txt`

Anotação curta dos intervalos conhecidos: velocidade `0..3400` e aceleração
`0..254`. A fonte executável dessas regras é `models/joint_config.py`.

### `comandos.txt`

Fragmento histórico de leitura com `ReadPosSpeed`. Não é módulo executável nem
documentação normativa.

### `external/`

Código, documentação e binários de projetos de terceiros, incluindo referências
de robótica e ferramentas do fabricante. Não importar automaticamente módulos
da aplicação a partir desse diretório e não editar seus arquivos como parte de
uma mudança comum no controlador.
