# Roadmap de Evolução — Braço Robótico 6-DOF

Este documento estabelece o planejamento técnico e a sequência evolutiva para o projeto de robótica, desde a consolidação da camada de baixo nível e segurança física até a implementação de Cinemática Direta (FK), Cinemática Inversa (IK) e Planejamento Cartesiano.

---

## 📍 Estado Atual da Base
- [x] **Configuração e Calibração Física:** 6 juntas calibradas e validadas (`robot_config.py`).
- [x] **Controle de Juntas (`Joint`):** Telemetria angular, conversão exata graus/counts e ativação segura de torque.
- [x] **Controle Coordenado do Braço (`RobotArm`):** Despacho atômico via `SyncWritePosEx`, validação de poses e timeout.
- [x] **Espelhamento e Trajetórias (`Teach & Repeat`):** Gravação manual livre, persistência em JSON (`recorded_actions/`), interpolação a 25Hz (LERP) e velocidade constante suavizada.
- [x] **Testes Automatizados:** 100+ testes unitários sem dependência de hardware conectado.

---

## 🎯 Fase 1: Pré-Cinemática (Segurança, Diagnóstico e Otimizações)

Antes de iniciar os cálculos matemáticos no espaço cartesiano (3D), estas frentes consolidam a robustez do hardware:

### 1.1 Telemetria de Saúde e Diagnóstico dos Servos
- **Leitura de Temperatura (°C):** Monitorar sobreaquecimento nos servos durante repouso sob torque.
- **Leitura de Tensão de Alimentação (V):** Detectar quedas de tensão na fonte de bancada.
- **Leitura de Carga / Corrente (*Load %*):** 
  - Detectar esforço excessivo por junta.
  - Implementar **Detecção de Colisão / Parada de Emergência (E-Stop):** se a carga ultrapassar o limiar de segurança, desativa o torque ou interrompe o movimento para proteger a estrutura mecânica.

### 1.2 Leitura Síncrona em Lote (`GroupSyncRead`)
- Substituir as 6 requisições seriais sequenciais de `arm.current_angles()` por um único pacote `SyncRead`.
- Elevar a frequência de telemetria para $>50\text{ Hz}$, liberando largura de banda no barramento serial RS485/UART.

### 1.3 Poses Padronizadas do Sistema (*Presets / Poses Nominais*)
- Adicionar configurações centrais de conveniência no `robot_config.py`:
  - `home`: Posição zero de referência ($0^\circ$ em todas as juntas).
  - `sleep` / `rest`: Braço totalmente dobrado e apoiado na bancada (posição segura para desligar torque sem queda livre).
  - `ready` / `standby`: Posição vertical de prontidão para trabalho.
  - `transport`: Posição compacta para transporte.
- Suporte a flags rápidas na CLI (ex.: `python main.py --preset rest`).

### 1.4 Perfil de Movimento Ponto a Ponto Suave (Trapezoidal / S-Curve)
- Gerador de transição contínua entre duas poses arbitrárias ($Pose_A \rightarrow Pose_B$) com aceleração progressiva, cruzeiro e desaceleração.
- Eliminação total de trancos mecânicos e vibrações na estrutura.

---

## 🚀 Fase 2: Modelagem Geométrica e Cinemática Direta (FK)

A transição para o espaço tridimensional $(X, Y, Z, \text{Roll}, \text{Pitch}, \text{Yaw})$:

### 2.1 Levantamento das Medidas Físicas dos Links
- Medição e registro milimétrico das distâncias entre eixos de rotação:
  - $L_1$: Altura da base ao eixo do ombro ($\text{mm}$).
  - $L_2$: Comprimento do braço principal (ombro ao cotovelo).
  - $L_3$: Comprimento do antebraço (cotovelo ao pulso).
  - $L_4$: Distância do pulso à ponta da garra (*Tool Center Point - TCP*).

### 2.2 Cinemática Direta (Forward Kinematics)
- **Convenção de Denavit-Hartenberg (DH Padrão / Modificado)** ou **Matrizes de Transformação Homogênea ($4 \times 4$)**.
- Entrada: Vetor de 6 ângulos $[\theta_1, \theta_2, \theta_3, \theta_4, \theta_5, \theta_6]$.
- Saída: Posição cartesiana do efetuador $(X, Y, Z)$ em mm e Matriz de Rotação / Quatérnions $(Q_w, Q_x, Q_y, Q_z)$.
- `arm.forward_kinematics(angles)` $\rightarrow$ `Pose3D(x, y, z, roll, pitch, yaw)`.

### 2.3 Modelo URDF / Visualizador 3D
- Geração do modelo URDF (*Unified Robot Description Format*).
- Visualização interativa em 3D (via script Python com `matplotlib`, `pybullet` ou `rerun`).

---

## 🔮 Fase 3: Cinemática Inversa (IK) e Controle Cartesiano

Capacidade de comandar o robô diretamente por coordenadas espaciais:

### 3.1 Cinemática Inversa (Inverse Kinematics)
- **Solução Numérica / Analítica:**
  - Entrada: Ponto no espaço $(X, Y, Z)$ e orientação desejada da garra.
  - Saída: Configuração de ângulos $[\theta_1, \dots, \theta_6]$ necessária para alcançar o ponto.
- Tratamento de singularidades mecânicas e seleção da melhor postura (cotovelo para cima / cotovelo para baixo).

### 3.2 Movimento Linear no Espaço (Interpolação Cartesiana / Linhas Retas)
- Traçar retas perfeitas no espaço tridimensional com o efetuador final (essencial para tarefas de Pick & Place e solda/desenho).
- Limites de envelope de trabalho (*Workspace Volume*).
