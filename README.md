<a id="readme-top"></a>

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/ats-sys/ats">
    <img src="images/logo.png" alt="Logo" width="80" height="80">
  </a>

  <h3 align="center">ATS: Automated Trading System</h3>

  <p align="center">
    Make Automated Trading Easy to Everyone!
    <br />
    <a href="https://ats-doc.gitbook.io/v1"><strong>Explore the Docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/ats-sys/ats/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    ·
    <a href="https://github.com/ats-sys/ats/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>
</div>


<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About the Project</a>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation-local">Installation (Local)</a></li>
        <li><a href="#installation-local">Installation (Docker)</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contributors">Contributors</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>


<!-- ABOUT THE PROJECT -->
<a id="about-the-project"></a>
## About The Project

[![Screen Shot][screenshot]](https://github.com/ats-sys/ats/images/screenshot.png)

ATS is a comprehensive automated trading system designed for traders and developers. With ATS, you can test, deploy, and manage custom trading strategies across various exchanges through an intuitive interface and API support.

Features:
* **Backtesting:**
  * Deploy strategies for real-time trading on supported exchanges, with live data feeds and execution.
* **Live Trading:**
  * Deploy strategies for real-time trading on supported exchanges, with live data feeds and execution.
* **Custom Strategies:**
  * Develop and integrate unique trading strategies tailored to your requirements. ATS provides a framework for implementing and testing new approaches. 
* **Exchange Connectivity:**
  * Connect to any trading exchange by creating custom exchange classes, enabling flexibility and support for various markets.
* **Reporting:**
  * Generate reports for backtesting and live trading environments. ATS offers insights into performance, risk metrics, and other essential analytics.
* **Custom Indicators:**
  * Create indicators that complement your strategy, providing unique signals and insights based on custom data.
* **Custom Report Generation:**
  * Tailor reports to specific needs, extracting insights from trade performance, risk, and market conditions.
* **API for Trading Jobs:**
  * Use ATS APIs to create, manage, and monitor trading jobs programmatically, providing automation capabilities.
Use ATS APIs to create, manage, and monitor trading jobs programmatically, providing automation capabilities. 
* **Simple Trading UI:**
  * A user-friendly interface for managing trades, viewing strategy performance, and monitoring real-time positions.
Of course, no one template will serve all projects since your needs may be different. So I'll be adding more in the near future. You may also suggest changes by forking this repo and creating a pull request or opening an issue. Thanks to all the people have contributed to expanding this template!

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- GETTING STARTED -->
<a id="getting-started"></a>
## Getting Started

This is an example of how you may give instructions on setting up your project locally.
To get a local copy up and running follow these simple example steps.

<a id="prerequisites"></a>
### Prerequisites

Following are the prerequisites you need to have beforehand.
* conda (Recommended)
  * You should have set up [Miniconda](https://docs.anaconda.com/miniconda/install/) (or [Anaconda](https://docs.anaconda.com/anaconda/install/)) setup on your system.
* [MongoDB](https://www.mongodb.com/docs/manual/administration/install-community/)
  * Makesure the MongoDB server is running on the system

### Installation (Local)

<a id="setup-option-1"></a>
#### Option 1 - conda:
  * simply run the `setup.sh` (for Linux) or `setup.bat` (for Windows) script to create a separate conda environment named `ats` with all the requirements needed for ATS. 
  * This will guid you through the installation with optional packages for AI-based strategies as well.

  * For Linux  
  ```shell
    ./setup.sh
  ```
  * For Windows
  ```shell
    .\setup.bat 
  ```

<a id="setup-option-2"></a>
#### Option 2 - conda:
  * You can create the conda environment named `ats` with the given `environment.yml` file.
  ```shell
    conda env create -f environment.yml
  ```
 * You may need to install the required AI-related packages manually if you are willing to run AI-based strategies.

<a id="setup-option-3"></a>
#### Option 3 - pip/conda:
* Use the `requirements.txt` file provided to install the required `Python` packages in an existing environment. 
* The package versions in `requirements.txt` have been tested for `Python 3.12` only. 
* If you are using a different `Python` version you may need to check for the compatible package versions.
  ```shell
    pip install -r requirements.txt
  ```
* You may need to install the required AI-related packages manually if you are willing to run AI-based strategies.

### Installation (Docker)
This option will be available soon :star_struck: 

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- USAGE EXAMPLES -->
## Usage

### Option 1:
* If you followed setup [Option 1](#setup-option-1) or [Option 2](#setup-option-2), you may use the provided `start.sh` (for Linux) or `start.bat` (for Windows) if you followed 
Refer our Documentation for all the information [Documentation][docs-url]

* For Linux  
  ```shell
    ./start.sh
  ```
  * For Windows
  ```shell
    .\start.bat 
  ```

### Option 2:
* Inside the created `Python` environment, you can simply run the `main.py` file.
  ```shell
      python -m ats.main
  ```
<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- ROADMAP -->
## Roadmap

- [x] Back trading Engine 
- [x] Live Trading Engine 
- [ ] Add More Exchanges
    - [x] Binance Spot
    - [ ] Binance Futures
    - [ ] More Exchanges
- [x] Realtime Plotting API
- [x] Realtime Logging API
- [ ] Optimize Back trading Engine
- [ ] Release the Docker Image
- [ ] Release the Python Package


See the [open issues](https://github.com/ats-sys/ats/issues) for a full list of proposed features (and known issues).

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- LICENSE -->
## License

Distributed under the Apache-2.0 License. See [`LICENSE`][license-url] for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTRIBUTORS -->
## Contributors

- Isuru S. Rajakaruna: [isururajakaruna@gmail.com](mailto:isururajakaruna@gmail.com)
- Sunanda Gamage: [rcsunanda@gmail.com](mailto:rcsunanda@gmail.com)
- Kasun Imesha Wickramasinghe: [iamkasunimesha@gmail.com](mailto:iamkasunimesha@gmail.com)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTACT -->
## Contact

- Project Link: [https://github.com/ats-sys/ats](https://github.com/ats-sys/ats)

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- MARKDOWN LINKS & IMAGES -->
[docs-url]: https://ats-doc.gitbook.io/v1
[license-url]: https://github.com/ats-sys/ats?tab=Apache-2.0-1-ov-file
[contributors-url]: https://github.com/ats-sys/ats/graphs/contributors
[screenshot]: images/screenshot.png
