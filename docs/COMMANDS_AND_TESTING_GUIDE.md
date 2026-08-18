# Guia de Comandos, Operação e Testes

Este guia documenta e explica todos os comandos disponíveis no projeto para execução de testes automatizados, leitura de calibração, verificação de movimentos e operação do braço robótico.

---

## ⚡ Tabela Rápida de Comandos

| Comando | Finalidade | Usa Hardware? | Liga Torque? |
| :--- | :--- | :---: | :---: |
| `python -m unittest discover -s tests -v` | Executa todos os testes unitários | ❌ Não (`FakeServo`) | ❌ Não |
| `python -m calibration.read_joint_position --servo-id 6` | Leitura manual de counts brutos | ✅ Sim | ❌ Não (Passivo) |
| `python -m calibration.test_joint_motion --joint gripper` | Teste de movimento supervisionado | ✅ Sim | ⚠️ Sim (Sob confirmação) |
| `python main.py` | Leitura de status de todas as juntas | ✅ Sim | ❌ Não |

---

## 1. Testes Automatizados (Sem Hardware)

Estes comandos executam a suíte de testes unitários isolada do mundo físico através de *test doubles* ([`FakeServo`](../tests/fake_servo.py)). Não requerem conexão USB nem energização dos motores.

### 1.1 Executar a suíte completa
```bash
python -m unittest discover -s tests -v
```
- **O que faz:** Descobre e roda todos os arquivos de teste dentro da pasta `tests/`.
- **Quando usar:** Antes e depois de qualquer alteração no código para garantir que nenhuma regressão foi introduzida.
- **Saída esperada:** `Ran 61 tests ... OK`.

### 1.2 Executar testes por módulo específico
```bash
# Testa apenas a classe Joint (métodos de torque, leitura, comando e move)
python -m unittest tests.test_joint -v

# Testa a configuração JointConfig (conversões graus <-> counts e limites)
python -m unittest tests.test_joint_config -v

# Testa o servo simulado (FakeServo)
python -m unittest tests.test_fake_servo -v

# Testa o leitor passivo de calibração
python -m unittest tests.test_read_joint_position -v

# Testa a rotina de teste de movimento da junta
python -m unittest tests.test_test_joint_motion -v
```

---

## 2. Leitura Passiva de Calibração (Hardware, Sem Torque)

Utilizada para calibrar novas juntas (medir zero mecânico, sentido e limites físicos). É estritamente passiva: nunca envia comandos de escrita nem energiza o motor.

```bash
python -m calibration.read_joint_position --servo-id <ID> [--port <PORT>] [--baudrate <BAUD>]
```

### Exemplo de uso:
```bash
python -m calibration.read_joint_position --servo-id 6 --port /dev/ttyUSB0 --baudrate 1000000
```

### Argumentos:
- `--servo-id` (obrigatório/padrão: `6`): ID individual do servo no barramento ($0..253$).
- `--port` (opcional, padrão: `/dev/ttyUSB0`): Porta serial de conexão.
- `--baudrate` (opcional, padrão: `1000000`): Taxa de transmissão serial.

### Controles durante a execução:
- `Enter`: Executa uma única leitura e exibe a posição atual em counts.
- `q` + `Enter` ou `Ctrl+C`: Encerra a ferramenta e fecha a porta serial.

---

## 3. Teste de Movimento Supervisionado (Hardware, Com Torque)

Utilizada para testar movimentos graduais e controlados de uma junta que já foi calibrada e cadastrada em [`robot_config.py`](../robot_config.py).

```bash
python -m calibration.test_joint_motion --joint <NOME_OU_ID> [--port <PORT>] [--baudrate <BAUD>]
```

### Exemplo de uso:
```bash
python -m calibration.test_joint_motion --joint gripper --port /dev/ttyUSB0 --baudrate 1000000
```

### Argumentos:
- `--joint` (opcional, padrão: `gripper`): Nome da junta (ex: `gripper`) ou ID numérico (ex: `6`).
- `--port` (opcional, padrão: `/dev/ttyUSB0`): Porta serial.
- `--baudrate` (opcional, padrão: `1000000`): Taxa de transmissão.

### Fluxo de segurança da ferramenta:
1. Exibe os limites operacionais calibrados e o estado inicial (posição e ângulo).
2. **Pede confirmação do operador** para habilitar o torque (`s/n`).
3. Ao confirmar, habilita o torque de forma segura (lê a posição atual antes de energizar).
4. Permite digitar o ângulo desejado (ex: `15.0`, `30.0`, `0.0`).
5. O método `Joint.move()` executa o comando e monitora até atingir a tolerância ou acusar timeout/erro.
6. Ao digitar `q`, solicita confirmação para desabilitar o torque e fecha a porta serial.

---

## 4. Execução da Aplicação Principal ([`main.py`](../main.py))

Ponto de entrada de alto nível do robô. Inicializa a porta serial, instancia todas as juntas cadastradas em [`robot_config.py`](../robot_config.py) e exibe o estado atual de cada uma.

```bash
python main.py
```

### Comportamento:
- Se `JOINT_CONFIGS` estiver vazio: Interrompe a execução imediatamente com erro de segurança antes de abrir a porta serial.
- Se houver juntas calibradas: Abre a porta, lê a posição e ângulo de cada junta e fecha a porta em `finally`.

---

## 5. Cuidados de Segurança Operacional

Antes de executar qualquer comando com hardware (`read_joint_position`, `test_joint_motion` ou `main.py`):
1. **Apoio Físico:** Certifique-se de que os elos do braço estão sustentados ou apoiados na bancada.
2. **Área Desimpedida:** Garanta que nenhuma pessoa, cabo ou objeto esteja no raio de alcance da articulação.
3. **Corte de Energia:** Mantenha a chave liga/desliga da fonte de alimentação dos servos sempre ao alcance da mão.
4. **Velocidade Reduzida:** Sempre inicie os testes com velocidade (`speed=400` ou menor) e aceleração suave (`acc=30`).
