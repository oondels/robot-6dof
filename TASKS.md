# Tarefas: braço robótico com múltiplas juntas

## Estado atual

- Etapa atual: **3 — Movimento individual robusto**.
- Última etapa concluída: **2 — Coordenadas físicas e calibração**.
- Desenvolvimento retomado após a documentação e a implementação isolada de
  `Joint.is_moving()`.
- Snapshot documentado: **37 testes passando**; `Joint.move()` ainda possui o
  comportamento antigo, sem espera e sem timeout.
- Regra inviolável: toda decisão, mudança aplicada ou evolução validada deve
  atualizar a documentação afetada no mesmo ciclo.
- Regra: somente uma etapa fica em andamento por vez.
- Código do robô é aplicado pelo estudante depois da explicação e do envio do
  código no chat.
- Movimentos físicos são executados somente pelo estudante.

## 0. Preparação

- [x] Criar `PLAN.md` na raiz.
- [x] Criar `TASKS.md` na raiz.
- [x] Registrar o estado atual da classe `Joint`.
- [x] Confirmar Python 3.12.3.
- [x] Confirmar a disponibilidade da classe `sms_sts`.
- [x] Confirmar resolução configurada de 4096 counts.
- [x] Confirmar que nenhum arquivo Python foi alterado nesta etapa.

### Observações da revisão inicial

- `Joint` já concentra leitura, torque, conversão e movimento individual.
- A porta serial é aberta em `main.py`, fora da classe, como desejado.
- `_validate_speed()` e `_validate_acceleration()` existem e são chamadas por
  `move()`, mas o construtor ainda não as chama.
- `from scservo_sdk import *` ainda está presente em `models/Joint.py`.
- A conversão atual usa `0°..360°` diretamente e ainda não representa zero
  mecânico, direção ou limites físicos próprios de cada junta.
- `move()` lê a posição imediatamente após enviar o comando e ainda não espera
  a conclusão do movimento.

## 1. Robustez da junta atual

- [x] Explicar invariantes do objeto e validação no construtor.
- [x] Corrigir imports e tipos.
- [x] Validar ID, nome, posição, velocidade e aceleração na construção.
- [x] Manter conexão e porta fora de `Joint`.
- [x] Criar um servo falso para testes.
- [x] Criar testes com `unittest`, sem dependências novas.
- [x] Revisar o código aplicado pelo estudante.
- [x] Executar os testes sem hardware.

### Critério de conclusão

Uma configuração inválida deve falhar durante a construção da junta, nenhum
teste deve acessar hardware e todos os testes da etapa devem passar.

Resultado: **concluído em 11 testes**, todos executados com `FakeServo`.

## 2. Coordenadas físicas e calibração

- [x] Explicar encoder, counts, zero mecânico, direção e limite angular.
- [x] Criar `JointConfig` imutável.
- [x] Implementar conversão entre graus físicos e counts.
- [x] Rejeitar configurações fora de `0..4095`.
- [x] Rejeitar intervalos que atravessem a volta do encoder.
- [x] Testar direção normal, direção invertida e limites.

### Critério de conclusão

Ângulos válidos devem fazer ida e volta pela conversão dentro da resolução de
um count; configurações inseguras devem ser rejeitadas antes de acessar o SDK.

Resultado: **concluído em 34 testes**. `JointConfig` concentra configuração,
calibração, conversão e validação; `Joint` concentra a operação do hardware.
Sem uma configuração calibrada, `main.py` recusa a execução antes de abrir a
porta serial.

## 3. Movimento individual robusto

- [x] Preparar `FakeServo` para simular posição e estado de movimento.
- [x] Implementar e testar `Joint.is_moving()`.
- [ ] Criar `Joint.command()` não bloqueante.
- [ ] Separar comando não bloqueante de movimento bloqueante.
- [ ] Implementar espera com tolerância, intervalo de consulta e timeout.
- [ ] Detectar servo parado fora do alvo.
- [ ] Manter torque habilitado após falha.
- [ ] Testar sucesso, parada, timeout e erro de comunicação.

### Critério de conclusão

O movimento deve terminar somente ao atingir a tolerância ou lançar um erro
diagnosticável e limitado por timeout.

## 4. Calibração física da primeira junta

- [ ] Criar rotina que apenas leia counts do servo informado.
- [ ] Preparar checklist de segurança para calibração.
- [ ] Medir zero da junta ID `6`.
- [ ] Determinar direção positiva.
- [ ] Medir limites seguros com margem mecânica.
- [ ] Registrar a configuração validada.
- [ ] Testar pequenos movimentos em baixa velocidade e aceleração.

### Critério de conclusão

A junta ID `6` deve alcançar pequenos ângulos físicos conhecidos sem atingir
batentes e retornar uma leitura coerente.

## 5. Controlador de múltiplas juntas

- [ ] Criar `RobotArm` com uma coleção ordenada de `Joint`.
- [ ] Rejeitar nomes e IDs duplicados.
- [ ] Implementar torque coletivo.
- [ ] Implementar leitura coletiva de ângulos.
- [ ] Validar poses completas por nome antes de qualquer escrita.
- [ ] Testar com duas ou mais juntas falsas.

### Critério de conclusão

O controlador deve rejeitar uma pose incompleta ou desconhecida sem enviar
nenhum comando e representar corretamente todas as juntas configuradas.

## 6. Movimento simultâneo

- [ ] Montar todos os alvos com `SyncWritePosEx`.
- [ ] Transmitir exatamente um pacote por pose.
- [ ] Limpar o buffer do SDK após sucesso ou falha.
- [ ] Aguardar todas as juntas.
- [ ] Informar qual junta falhou e manter o torque.
- [ ] Testar transmissão, espera e falhas com servo falso.

### Critério de conclusão

Uma pose válida deve gerar um pacote sincronizado e retornar os ângulos finais;
qualquer falha deve abortar com diagnóstico e buffer limpo.

## 7. Teste gradual no hardware

- [ ] Calibrar a segunda junta.
- [ ] Testar cada junta separadamente.
- [ ] Apoiar o braço e liberar a área de movimento.
- [ ] Habilitar torque mantendo as posições atuais como alvos.
- [ ] Executar uma pose pequena com duas juntas.
- [ ] Confirmar tolerância e comportamento de falha.
- [ ] Repetir a integração gradualmente até seis juntas.

### Critério de conclusão

Duas juntas devem iniciar praticamente juntas, alcançar uma pose segura dentro
da tolerância e interromper a operação com diagnóstico quando houver falha.

## 8. Consolidação

- [ ] Revisar scripts experimentais substituídos.
- [ ] Remover arquivos obsoletos somente após autorização.
- [ ] Documentar instalação, inicialização, calibração e operação segura.
- [ ] Registrar extensões futuras para trajetória e cinemática.

### Critério de conclusão

O projeto deve possuir uma base documentada, testável e reutilizável para seis
juntas, sem incluir prematuramente cinemática ou controle de garra.
