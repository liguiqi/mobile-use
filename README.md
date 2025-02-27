# Mobile Use 🚀
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> A GUI agent system for operating smartphones through natural language commands.

**Mobile Use** is a groundbreaking open-source project that automates smartphone operations via natural language instructions. By combining the semantic and visual understanding capabilities of Vision-Language Models (VLM) with the system-level control of Android Debug Bridge (ADB), it allows you to interact directly with your phone using human language.

[ English | [中文](docs/README_zh.md) ]


![AI Did My Groceries](https://madeagents.oss-cn-beijing.aliyuncs.com/TurnOnBluetoothAndWIFI_en_2x.gif)


## ✨ Key Features
- **Natural Language Interaction**: Control your phone using everyday English/Chinese.
- **Smart Element Recognition**: Automatically parses GUI layouts and identifies operational targets.
- **Multi-task Orchestration**: Supports decomposition of complex instructions and multi-step operations.

## 🚀 Quick Start
### Prerequisites
- Python 3.10+
- Enable developer mode on your phone
- [ADB environment](https://developer.android.com/tools/adb)


### Installation
> `mobile-use` requires [adb](https://developer.android.com/tools/adb) to control the phone, so relevant services and connections must be installed and configured in advance.

#### 1. Clone the repository
```
git clone https://github.com/MadeAgents/mobile-use
```

#### 2. Install dependencies
```
cd mobile-use
pip install .
```

#### 3. Verify the adb is connected
Run the `adb devices` (Windows: `adb.exe devices`) command on the command line terminal. If the device serial_no is listed, the connection is successful. The correct log is as follows:
```
List of devices attached
a22d0110        device
```

#### 4. Launch the webui service
```
python webui.py
```

### Usage
Once the service starts successfully, open the address http://127.0.0.1:7860 in your browser to access the WebUI page, as shown below:
![](static/demo.png)

Click VLM Configuration to set the Base URL and API Key of the multimodal large language model. It is recommended to use the multimodal large language model of Qwen2.5-VL series.
![alt text](docs/assets/vlm_configuration.png)

Input task descriptions in the input box at the lower left corner, click start to execute tasks.


## 🎉 More Demo
Case1：Search the latest news of DeepSeek-R2 in Xiaohongshu APP and forward one of the news to the Weibo App
![](docs/assets/search_forward_2x.gif)

Case2：Order 2 Luckin coffees with Meituan, 1 hot raw coconut latte standard sweet, and 1 cold light jasmine
![](docs/assets/order_coffee_en_2x.gif)

Case3：用美团点一杯咖啡，冰的，标准糖
![](docs/assets/demo01_2x.gif)

Case4：用美团帮我点2杯瑞幸咖啡，要生椰拿铁标准糖、热的
![](docs/assets/order_coffee_zh_2x.gif)

Case5：在浏览器找一张OPPO Find N5图片，询问DeepSeek应用该手机介绍信息，将找到的图片和介绍信息通过小红书发布
![](docs/assets/demo03_2x.gif)

Case6：帮我去OPPO商城、京东、以及淘宝分别看一下oppofind n5售价是多少
![](docs/assets/oppofindn5_price_zh_2x.gif)


## 🌱Contributing
We welcome all forms of contributions! Please read our contribution guide to learn about:
- How to submit an issue to report problems.
- The process of participating in feature development.
- Code style and quality standards.
- Methods for suggesting documentation improvements.

## 📜 License
This project is licensed under the MIT License, which permits free use and modification of the code but requires retaining the original copyright notice.

## 📚 Citation
If you have used this project in your research or work, please cite:
```
@software{
  title = {Mobile Use: A GUI agent system for operating smartphones through natural language commands.},
  author = {Jiamu Zhou, Ning Li, Qiuying Peng, Xiaoyun Mo, Qiqiang Lin, Jun Wang, Yin Zhao},
  year = {2025},
  publisher = {GitHub},
  url = {https://github.com/MadeAgents/mobile-use}
}
```

## 🤝 Acknowledgements
This repo benefits from [Gradio](https://www.gradio.app) and [Qwen2.5-VL](https://huggingface.co/collections/Qwen/qwen25-vl-6795ffac22b334a837c0f9a5).Thanks for their wonderful works.
