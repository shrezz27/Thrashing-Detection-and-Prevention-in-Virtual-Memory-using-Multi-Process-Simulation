# Thrashing-Detection-and-Prevention-in-Virtual-Memory-using-Multi-Process-Simulation
Multi-process virtual memory simulator demonstrating page replacement, thrashing detection, and working set–based prevention.
## 📌 Overview

This project is an interactive **Operating Systems simulator** that demonstrates how **virtual memory management** works in a multi-process environment. It visualizes **page replacement algorithms**, detects **thrashing**, and applies **working set–based prevention techniques** to stabilize system performance.

---

## 🚀 Features

* 🔄 **Multi-Process Simulation (Round Robin Scheduling)**
* 📄 **Page Replacement Algorithms**

  * FIFO (First-In First-Out)
  * LRU (Least Recently Used)
  * Optimal
* ⚠️ **Thrashing Detection**

  * Based on system-wide page fault rate
* 🛠️ **Thrashing Prevention**

  * Suspends processes dynamically
* 🧠 **Working Set Model (Denning)**

  * Tracks active pages using sliding window (Δ)
* 📊 **Graph Visualization**

  * CPU Utilization vs Processes
  * Page Fault Rate Trends
  * Working Set Size over Time
* 🖥️ **GUI Interface**

  * Built using Tkinter for interactive simulation

---

## 🧠 Key Concepts Demonstrated

* Virtual Memory & Paging
* Page Fault Handling
* Thrashing Phenomenon
* Working Set Model
* Multi-Process Scheduling
* Memory Allocation Strategies

---

## ⚙️ How It Works

1. Multiple processes generate page references.
2. Pages are loaded into limited RAM frames.
3. If a page is missing → **Page Fault occurs**.
4. Replacement algorithms decide which page to remove.
5. If fault rate becomes too high → **Thrashing detected**.
6. System suspends high-fault processes to recover.
7. Working set model estimates memory demand dynamically.

---

## 📂 Project Structure

```
├── main.py              # Entry point
├── gui.py               # Tkinter GUI
├── memory_core.py       # RAM + frame management
├── algorithms.py        # FIFO, LRU, Optimal
├── process_sim.py       # Multi-process scheduler
├── working_set.py       # Working Set Model
├── visualizer.py        # Graphs & analysis
```

---

## 📊 Sample Output

* High fault rate → CPU utilization drops to 0% (Thrashing)
* After prevention → CPU stabilizes
* Graphs show Denning’s Thrashing Curve

---

## 🧪 Technologies Used

* Python
* Tkinter (GUI)
* Matplotlib (Visualization)

---

## 📈 Future Improvements

* Real frame deallocation on process suspension
* Integration of working set with frame allocation
* Advanced scheduling algorithms
* Disk I/O simulation for page faults

---

## ⭐ Why This Project?

This project bridges **theory and practical understanding** of OS concepts like thrashing, making it easier to visualize and analyze real-world memory behavior.

---

