# Robotics — braço robótico 6-DOF

Base didática em Python para controlar, de forma gradual e segura, um braço
robótico de seis graus de liberdade usando servos compatíveis com o SDK
`scservo_sdk`/SMS-STS.

O projeto ainda está em desenvolvimento. Atualmente ele possui uma abstração
testada para configuração física de juntas, controle individual básico e um
servo falso para testes sem hardware. Controle coordenado de múltiplas juntas,
timeout de movimento e cinemática ainda não estão implementados.

## Estado atual

| Área | Estado |
| --- | --- |
| Configuração física de uma junta | Implementada e testada |
| Conversão entre graus e counts | Implementada e testada |
| Leitura e controle de torque | Implementados e testados com servo falso |
| Leitura do estado de movimento | Implementada e testada |
| Simulação de movimento | Implementada no `FakeServo` |
| Movimento individual com timeout | Em desenvolvimento |
| Controle de múltiplas juntas | Planejado |
| Movimento simultâneo com SyncWrite | Planejado |
| Cinemática direta/inversa | Fora do escopo atual |
| Configuração física real | Pendente de calibração |

A suíte atual contém **37 testes sem hardware**. `robot_config.py` mantém
`JOINT_CONFIGS` vazio; por isso, `main.py` recusa a execução antes de abrir a
porta serial.

> **Atenção:** o método `Joint.move()` atual ainda não espera o servo chegar ao
> destino. Ele envia o comando e lê a posição imediatamente. Não o trate como
> movimento bloqueante ou concluído.

## Leitura rápida

- [Arquitetura](docs/ARCHITECTURE.md): responsabilidades, fluxos e modelo
  angular.
- [Referência dos módulos](docs/MODULES.md): função e API de cada arquivo do
  projeto.
- [Segurança, calibração e testes](docs/SAFETY_AND_TESTING.md): cuidados com o
  hardware, estratégia de testes e limitações.
- [Plano de evolução](PLAN.md): arquitetura pretendida até múltiplas juntas.
- [Tarefas e progresso](TASKS.md): etapa atual e critérios de conclusão.

## Estrutura

```text
robotics/
├── main.py                    # composição e entrada segura da aplicação
├── robot_config.py            # configurações calibradas das juntas
├── models/
│   ├── Joint.py               # operação de uma junta no hardware
│   └── joint_config.py        # calibração, limites e conversões
├── utils/
│   └── validation.py          # valida respostas do SDK
├── tests/
│   ├── fake_servo.py          # substituto do servo real
│   ├── test_joint.py
│   ├── test_joint_config.py
│   └── test_fake_servo.py
├── docs/                      # documentação técnica e operacional
├── PLAN.md                    # decisões e arquitetura futura
└── TASKS.md                   # checklist de desenvolvimento
```

O diretório `external/` contém referências e projetos de terceiros. Ele não faz
parte da implementação própria descrita nesta documentação e não deve ser
alterado ao evoluir os módulos principais.

## Conceitos centrais

Uma junta é dividida em duas responsabilidades:

```text
JointConfig                         Joint
configuração física                 operação em tempo de execução
─────────────────────────           ───────────────────────────
ID e nome                           comunicação com o SDK
zero mecânico                       leitura da posição
direção positiva                    torque
limites angulares                   envio de movimento
graus ↔ counts                      diagnóstico de comunicação
```

Essa separação permite usar a mesma lógica `Joint` para todas as juntas do
braço, mudando apenas a configuração calibrada de cada uma.

## Executar os testes

Na raiz do projeto:

```bash
python -m unittest discover -s tests -v
```

Os testes usam `FakeServo`; não criam `PortHandler`, não abrem `/dev/ttyUSB0` e
não movimentam motores.

## Dependências

O código foi verificado com Python 3.12. A dependência principal do controle é:

```text
ftservo-python-sdk==2.0.0
```

O arquivo `requirements.txt` contém também dependências de outras ferramentas
do ambiente e uma dependência Git via SSH. Portanto, ele não representa ainda
um conjunto mínimo de dependências do controlador robótico.

## Orientação para humanos e IAs

Antes de modificar o projeto:

1. Leia este arquivo e `docs/MODULES.md`.
2. Consulte `TASKS.md` para saber qual etapa está ativa.
3. Use `PLAN.md` para distinguir implementação atual de arquitetura futura.
4. Execute a suíte antes e depois de qualquer mudança.
5. Não execute `main.py` nem comandos de torque/movimento sem calibração e
   autorização explícita para operar o hardware.
6. Não use os valores `2048`, `-90°` e `90°` dos testes como calibração real.
7. Atualize a documentação afetada junto com toda decisão ou mudança validada;
   código e documentação devem representar o mesmo estado do projeto.

O método de desenvolvimento é incremental: uma tarefa por vez, código
explicado, testes sem hardware e validação física gradual.
