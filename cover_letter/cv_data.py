"""
Structured CV data for cover letter generation.
All text snippets are genuine — sourced directly from main.tex.

text_general  → concise (~2 sentences), suits a broader application
text_specific → detailed (~3-4 sentences, includes metrics), suits a targeted application
"""

PERSONAL = {
    "name": "Sahil Sanjay Rajpurkar",
    "address": "Dortmund, Germany",
    "phone": "+49 17671678983",
    "email": "sahilrajpurkar1998@gmail.com",
    "linkedin": "linkedin.com/in/sahilrajpurkar",
    "github": "github.com/sahilrajpurkar03",
    "education": "M.Sc. Automation and Robotics, TU Dortmund (2022–2025)",
    "degree_short": "M.Sc. Automation and Robotics",
    "university": "TU Dortmund",
}

# ── Experience entries ──────────────────────────────────────────────────────
# base_weight: tiebreaker — current / recent roles ranked higher.

EXPERIENCES = [
    {
        "id": "porsche",
        "title": "Praktikant – Humanoid Robotics Development & Validation",
        "company": "Porsche Engineering",
        "period": "April 2026 – present",
        "location": "Mönsheim, Germany",
        "tags": [
            "ros2", "humanoid", "navigation", "localization", "mapping",
            "dds", "websocket", "isaac sim", "mujoco", "mobile robot",
            "quadruped", "wheeled robot", "autonomous", "simulation",
            "robot", "robotics", "autonomous systems",
        ],
        "text_general": (
            "In my current internship at Porsche Engineering, I develop localization, "
            "mapping, and navigation pipelines for humanoid, quadruped, and wheeled "
            "mobile robot platforms using ROS2, DDS, and WebSocket-based communication architectures."
        ),
        "text_specific": (
            "In my current internship at Porsche Engineering, I develop localization, "
            "mapping, and navigation pipelines for humanoid, quadruped, and wheeled "
            "mobile robot platforms using ROS2, DDS, and WebSocket-based communication. "
            "I simulate and validate multi-platform robot behavior in NVIDIA Isaac Sim "
            "and MuJoCo prior to real-world deployment, ensuring robust performance "
            "across distinct hardware configurations."
        ),
        "base_weight": 3,
    },
    {
        "id": "tu_dortmund",
        "title": "Research Assistant",
        "company": "Communication Networks Institute, TU Dortmund",
        "period": "April 2023 – January 2026",
        "location": "Dortmund, Germany",
        "tags": [
            "lidar", "3d detection", "object detection", "ros2", "python",
            "isaac sim", "mmdetection", "slam", "lio-slam", "point cloud",
            "moveit", "manipulation", "dual-arm", "xarm", "mmwave",
            "drone", "uav", "boston dynamics", "spot", "sensor fusion",
            "robot", "robotics", "research", "c++",
        ],
        "text_general": (
            "As a Research Assistant at TU Dortmund for nearly three years, I developed "
            "a LiDAR-based 3D object detection pipeline in NVIDIA Isaac Sim and ROS2, "
            "built a dual-arm air hockey system with ROS2 MoveIt, and integrated mmWave "
            "health sensors on Boston Dynamics Spot for rescue robotics demonstrations at the DRZ."
        ),
        "text_specific": (
            "As a Research Assistant at TU Dortmund for nearly three years, I developed "
            "a LiDAR-based 3D object detection pipeline with LIO-SLAM and MMDetection "
            "in NVIDIA Isaac Sim and ROS2, implemented point cloud coloring from camera feed, "
            "and built a dual-arm air hockey system using UFactory xArms with ROS2 MoveIt. "
            "Additionally, I conducted drone interference analysis with Aaronia Spectran V6 "
            "and assisted in integrating mmWave health sensors on Boston Dynamics Spot "
            "and Scout robots for rescue robotics demonstrations at the DRZ."
        ),
        "base_weight": 2,
    },
    {
        "id": "betic",
        "title": "Research Assistant",
        "company": "BETiC, IIT Bombay",
        "period": "July 2020 – September 2022",
        "location": "Mumbai, India",
        "tags": [
            "stm32", "esp32", "embedded", "rtos", "uart", "spi", "i2c",
            "pcb", "ci/cd", "jenkins", "medical device", "iso 13485",
            "hil", "hardware-in-loop", "atmel", "microcontroller",
            "firmware", "embedded c", "arm", "kicad", "altium",
        ],
        "text_general": (
            "Prior to my studies, I led medical device development at BETiC/IIT Bombay, "
            "integrating sensors with STM32 and ATMEL microcontrollers via UART, SPI, and I2C, "
            "implementing real-time Embedded C algorithms with RTOS, and managing CI/CD "
            "workflows with Git and Jenkins."
        ),
        "text_specific": (
            "Prior to my studies, I led medical device projects at BETiC/IIT Bombay — "
            "including ventilators and portable oxygen generators compliant with ISO 13485. "
            "I integrated medical-grade sensors with STM32 and ATMEL microcontrollers via "
            "UART, SPI, and I2C, implemented RTOS-based real-time control algorithms in "
            "Embedded C, and conducted hardware-in-loop (HIL) testing with CI/CD "
            "managed through Git and Jenkins."
        ),
        "base_weight": 1,
    },
]

# ── Thesis & Project entries ────────────────────────────────────────────────

PROJECTS = [
    {
        "id": "master_thesis",
        "title": "Master Thesis: Radar-Based Object Detection for Logistics",
        "period": "Aug 2024 – Feb 2025",
        "tags": [
            "radar", "mmwave", "object detection", "yolov7", "detectron2",
            "openpcdet", "pv-rcnn", "3d detection", "point cloud", "logistics",
            "machine learning", "dataset", "ml", "deep learning", "ti iwr6843",
        ],
        "text_general": (
            "My Master's thesis focused on ML-based radar object detection for "
            "logistics automation using TI mmWave radar, training YOLOv7, "
            "Detectron2, and PV-RCNN models on a custom indoor dataset."
        ),
        "text_specific": (
            "My Master's thesis developed an ML-based detection pipeline for "
            "logistics automation using TI IWR6843ISK mmWave radar. "
            "I collected a custom indoor dataset of forklifts, robots, and KLTs, "
            "trained 2D and 3D detection models (YOLOv7, Detectron2, PV-RCNN via OpenPCDet), "
            "and validated results against a Vicon motion capture system, "
            "achieving a mean centroid error of 0.4–0.5 m."
        ),
        "base_weight": 2,
    },
    {
        "id": "chatpicker",
        "title": "Robotic Arm Pick-and-Place Chatbot",
        "tags": [
            "ros2", "isaac sim", "moveit", "fastapi", "yolov8", "llm",
            "pick and place", "manipulation", "natural language", "ollama",
            "6-axis", "robotic arm", "robot", "simulation",
        ],
        "text_general": (
            "In a personal project, I simulated pick-and-place tasks on a 6-axis "
            "robotic arm via LLM chatbot commands, integrating ROS2, NVIDIA Isaac Sim, "
            "MoveIt, and YOLOv8 for object detection."
        ),
        "text_specific": (
            "In a personal project, I built a system for controlling a 6-axis robotic "
            "arm via natural language chatbot commands, integrating ROS2, NVIDIA Isaac Sim, "
            "ROS2 MoveIt for motion planning, YOLOv8 OBB for object detection, "
            "and a local LLM (Phi3 via Ollama) served through a FastAPI backend."
        ),
        "base_weight": 1,
    },
    {
        "id": "ur5_il",
        "title": "UR5 Object Alignment via Imitation Learning",
        "tags": [
            "isaac sim", "imitation learning", "diffusion policy", "ur5",
            "manipulation", "lerobot", "data collection", "simulation",
            "machine learning", "robot learning",
        ],
        "text_general": (
            "I also trained a UR5 arm for object alignment in NVIDIA Isaac Sim "
            "using imitation learning and diffusion policy algorithms via the LeRobot framework."
        ),
        "text_specific": (
            "I trained a UR5 robotic arm for precise object alignment in NVIDIA Isaac Sim "
            "using imitation learning and diffusion policy algorithms through the LeRobot "
            "framework, managing structured episode data collection and comprehensive "
            "model evaluation in photorealistic simulations."
        ),
        "base_weight": 1,
    },
    {
        "id": "sipiemc",
        "title": "SI/PI/EMC Design Chatbot",
        "tags": [
            "pcb", "signal integrity", "power integrity", "emc",
            "rasa", "nlu", "ltspice", "ai chatbot", "pcb design",
        ],
        "text_general": (
            "Earlier, I built an AI-based RASA NLU chatbot assisting PCB designers "
            "with signal integrity, power integrity, and EMC issues, integrated "
            "with LTSpice APIs for real-time electrical simulations."
        ),
        "text_specific": (
            "Earlier, I developed an AI-based RASA NLU chatbot for PCB designers "
            "addressing signal integrity, power integrity, and EMC analysis, "
            "with LTSpice API integration for real-time on-platform electrical "
            "simulations and design optimisation."
        ),
        "base_weight": 0,
    },
]

# ── Top-level skill phrases (used in opening paragraph) ─────────────────────
# Ordered by relevance to robotics roles.
SKILL_PHRASES = [
    ("ros2",            "ROS2"),
    ("ros",             "ROS/ROS2"),
    ("isaac sim",       "NVIDIA Isaac Sim"),
    ("mujoco",          "MuJoCo"),
    ("moveit",          "MoveIt"),
    ("lidar",           "LiDAR-based perception"),
    ("radar",           "mmWave radar"),
    ("object detection","object detection"),
    ("slam",            "SLAM"),
    ("navigation",      "autonomous navigation"),
    ("manipulation",    "robotic manipulation"),
    ("humanoid",        "humanoid robotics"),
    ("simulation",      "robot simulation"),
    ("embedded",        "embedded systems"),
    ("stm32",           "STM32/ARM embedded"),
    ("python",          "Python"),
    ("c++",             "C++"),
    ("machine learning","machine learning"),
    ("deep learning",   "deep learning"),
    ("computer vision", "computer vision"),
    ("opencv",          "OpenCV"),
    ("tensorflow",      "TensorFlow/PyTorch"),
    ("pytorch",         "TensorFlow/PyTorch"),
    ("sensor fusion",   "sensor fusion"),
    ("docker",          "Docker/Linux"),
    ("ci/cd",           "CI/CD"),
]
