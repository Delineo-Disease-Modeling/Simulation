# Quick Start Guide

## Getting Started with DMP

### 1. Installation
```bash
# Clone the repository
git clone [repository-url]
cd Simulation/dmp

# Install dependencies
pip install -r requirements.txt
```

### 2. Choose Your Interface

#### Option A: Web Interface (Recommended for beginners)
```bash
streamlit run app/graph_visualization.py
```
- Open your browser to the provided URL
- Use the interactive web interface to create and manage state machines
- No programming knowledge required

#### Option B: Command Line Interface
```bash
python3 -m cli.user_input \
    --age 25 \
    --vaccination_status Vaccinated \
    --sex F \
    --variant Omicron
```

#### Option C: REST API (For developers)
```bash
# Start the API server
uvicorn api.dmp_api_v2:app --reload

# Make API calls
curl -X POST http://localhost:8000/initialize \
     -H "Content-Type: application/json" \
     -d '{"use_state_machines": true}'
```

### 3. Your First Simulation

1. **Start the web interface**: `streamlit run app/graph_visualization.py`
2. **Go to "State Machine Creator"** tab
3. **Select a disease template** (e.g., COVID-19)
4. **Add demographics** (Age, Sex, Vaccination Status)
5. **Create your state machine** with the visual editor
6. **Save your state machine**
7. **Go to "State Machine Manager"** to run simulations

### 4. Understanding the Results

The simulation will show you:
- **Timeline**: Step-by-step disease progression
- **Duration**: Time spent in each state
- **Final State**: Where the individual ends up
- **Statistics**: For multi-run simulations

### 5. Next Steps

- **Read the full documentation**: See `docs/API_DOCUMENTATION.md`
- **Explore disease templates**: Try different diseases and variants
- **Create custom models**: Build your own state machines
- **Compare models**: Use the comparison tool to analyze differences

## Common Questions

**Q: What's the difference between the interfaces?**
A: 
- **Web Interface**: Best for exploration and learning
- **CLI**: Good for batch processing and scripting
- **API**: Best for integration with other applications

**Q: How do I create my own disease model?**
A: Use the "State Machine Creator" in the web interface, or start with a template and modify it.

**Q: Can I import existing data?**
A: Yes, you can import state machines via JSON files in the web interface.

**Q: How accurate are the simulations?**
A: Accuracy depends on the quality of your state machine parameters. Start with the provided templates and adjust based on your specific needs. 