# Smart Cities Data Tools  
### Micromobility, Curbside, and Transit Data Engineering Toolkit

This repository contains a collection of **data ingestion, processing, and visualization tools** developed for **smart city mobility systems**, including **micromobility (bike-share)**, **curbside data**, and **public transit (GTFS)**.

The tools automate the collection of mobility data from public APIs and structured feeds, store historical records in databases, and generate metrics and visualizations to support **mobility analysis**, **system monitoring**, and **urban planning workflows**.

This repository reflects real-world workflows involving **scheduled cloud data pipelines**, **API ingestion**, and **transportation analytics**.

---

# Project Overview

The primary goals of this project were to:

- **Automate micromobility (bike-share) data collection**
  - Retrieve **GBFS (General Bikeshare Feed Specification)** data from Bogotá bike-share systems  
  - Collect station and usage data at regular intervals  
  - Store hourly system snapshots for **historical trend analysis**

- **Build a scheduled cloud ingestion pipeline**
  - Configure **AWS EventBridge** scheduled tasks  
  - Trigger **AWS Lambda** functions to collect GBFS data  
  - Store usage data into a database for long-term storage  
  - Enable historical system performance tracking

- **Explore curbside and parking-related datasets**
  - Perform exploratory data analysis (EDA) on curbside datasets  
  - Analyze usage and operational trends  
  - Generate visual summaries for mobility insights
 
- **Process public transit data (GTFS)**
  - Retrieve **GTFS static and realtime data**  
  - Process transit feeds from **Durham Region Transit**  
  - Visualize routes, stops, and service activity  
  - Generate transit system metrics and performance indicators

- **Generate analytics and visualizations**
  - Create performance metrics across mobility systems  
  - Produce charts and spatial outputs  
  - Support system monitoring and operational analysis

- **Build reusable mobility data utilities**
  - Standardize data ingestion workflows  
  - Create reusable helper modules  
  - Support extensibility across multiple mobility domains

This project supports **smart city mobility analytics**, **transportation system monitoring**, and **urban data engineering workflows** and is organized into three primary mobility domains: **Active Mobility**, **Curbside**, and **Transit**. Each module focuses on collecting, processing, and analyzing data from different urban mobility systems.

---

## Active Mobility

The **Active Mobility** module focuses on **micromobility systems**, specifically bike-share data collected using the **GBFS (General Bikeshare Feed Specification)**.

This module automates the retrieval of bike-share system data from Bogotá using a **scheduled AWS pipeline**, where **EventBridge triggers AWS Lambda functions** to collect system data at regular intervals. The data is stored in a database to build **hourly historical records**, enabling long-term trend analysis, usage monitoring, and performance evaluation of bike-share systems.

---

## Curbside

The **Curbside** module focuses on **curbside and parking-related datasets**, supporting exploratory analysis of operational and usage patterns.

This module includes tools for **data exploration and visualization**, helping identify patterns in curbside activity, space utilization, and operational trends. The workflows support analysis used in **parking management**, **curbside allocation planning**, and **urban mobility strategy development**.

---

## Transit

The **Transit** module processes **public transit data** using **GTFS static and realtime feeds**.
This module retrieves transit data from Durham Region Transit and generates **visualizations and performance metrics** related to routes, stops, and service activity. It supports spatial analysis of transit networks and enables monitoring of system behavior using standardized transit data formats.
