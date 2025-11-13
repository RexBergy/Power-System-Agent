from typing import Dict, List, Optional, Tuple, Any, Union
import pandapower as pp
from mcp.server.fastmcp import FastMCP
import logging
import pandas as pd
import numpy as np
from pandapower.timeseries.data_sources.frame_data import DFData
from pandapower.control import ConstControl
from pandapower.timeseries import run_timeseries

import sys
import os
import json as js
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.utils import PowerError, power_mcp_tool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server with logging
logger.info("Initializing Pandapower Analysis Server")
mcp = FastMCP("Pandapower Analysis Server")

# Global variable to store the current network
_current_net = None

def _get_network() -> pp.pandapowerNet:
    """Get the current pandapower network instance.
    
    Returns:
        pp.pandapowerNet: The current network or raises error if none loaded
    """
    global _current_net
    
    if _current_net is None:
        raise RuntimeError("No pandapower network is currently loaded. Please create or load a network first.")
    return _current_net


@power_mcp_tool(mcp)
def create_empty_network() -> Dict[str, Any]:
    """Create an empty pandapower network.
    
    Returns:
        Dict containing status and network information
    """
    logger.info("Creating an empty pandapower network")
    global _current_net
    try:
        _current_net = pp.create_empty_network()
        raise Exception("test")
        return {
            "status": "success",
            "message": "Empty network created successfully",
            "network_info": {
                "buses": len(_current_net.bus),
                "lines": len(_current_net.line),
                "trafos": len(_current_net.trafo)
            }
        }
    except Exception as e:
        return PowerError(
            status="error",
            message=f"Failed to create empty network: {str(e)}"
        )

@power_mcp_tool(mcp)
def load_network(file_path: str) -> Dict[str, Any]:
    """Load a pandapower network from a file.
    
    Args:
        file_path: Path to the network file (.json, .p)
        
    Returns:
        Dict containing status and network information
    """
    logger.info(f"Loading network from file: {file_path}")
    global _current_net
    try:
        if file_path.endswith('.json'):
            _current_net = pp.from_json(file_path)
        elif file_path.endswith('.p'):
            _current_net = pp.from_pickle(file_path)
        else:
            raise ValueError("Unsupported file format. Use .json or .p files.")
            
        return {
            "status": "success",
            "message": f"Network loaded successfully from {file_path}",
            "network_info": {
                "buses": len(_current_net.bus),
                "lines": len(_current_net.line),
                "trafos": len(_current_net.trafo)
            }
        }
    except FileNotFoundError:
        return PowerError(
            status="error",
            message=f"File not found: {file_path}"
        )
    except ValueError as ve:
        return PowerError(
            status="error",
            message=str(ve)
        )
    except Exception as e:
        return PowerError(
            status="error",
            message=f"Failed to load network: {str(e)}"
        )

@power_mcp_tool(mcp)
def run_power_flow(algorithm: str = 'nr', calculate_voltage_angles: bool = True, 
                  max_iteration: int = 10, tolerance_mva: float = 1e-8) -> Dict[str, Any]:
    """Run power flow analysis on the current network.
    
    Args:
        algorithm: Power flow algorithm ('nr' for Newton-Raphson, 'bfsw' for backward/forward sweep)
        calculate_voltage_angles: Consider voltage angles in calculation
        max_iteration: Maximum number of iterations
        tolerance_mva: Convergence tolerance in MVA
        
    Returns:
        Message with status and saved path results
    """
    logger.info(f"Running power flow analysis")
    try:
        net = _get_network()
        pp.runpp(net, algorithm=algorithm, calculate_voltage_angles=calculate_voltage_angles,
                max_iteration=max_iteration, tolerance_mva=tolerance_mva)
        
        # Extract key results
        results = {
            "bus_results": net.res_bus.to_dict(),
            "line_results": net.res_line.to_dict(),
            "trafo_results": net.res_trafo.to_dict(),
            "converged": net.converged
        }
        # with open(save_file, "r") as f:
        #     js.dump(
        #         {
        #         "status": "success",
        #         "message": "Power flow calculation completed successfully" if net.converged else "Power flow did not converge",
        #         "results": results
        #         },
        #         f
        #     )

        return f"Powerflow completed sucessfully. Converged: {net.converged}"
    except RuntimeError as re:
        return PowerError(
            status="error",
            message=str(re)
        )
    except Exception as e:
        return PowerError(
            status="error",
            message=f"Power flow calculation failed: {str(e)}"
        )

@power_mcp_tool(mcp)
def run_contingency_analysis(save_file : str,
                            contingency_type: str = "N-1", 
                           elements: Optional[List[str]] = None) -> Dict[str, Any]:
    """Run contingency analysis on the current network.
    
    Args:
        save_file: A json file path (.json) to save the results
        contingency_type: Type of contingency analysis ("N-1" or "N-2")
        elements: List of specific elements to analyze (optional)
        
    Returns:
        Message with status and saved path results
    """
    logger.info(f"Running contingency analysis in {save_file}")
    try:
        net = _get_network()
        
        # Store original state
        orig_net = net.deepcopy()
        results = []
        
        # Define elements to analyze
        if elements is None:
            elements = ['line', 'trafo']
            
        # Perform contingency analysis
        for element_type in elements:
            for idx in net[element_type].index:
                # Create contingency by taking element out of service
                contingency_net = orig_net.deepcopy()
                contingency_net[element_type].at[idx, 'in_service'] = False
                
                try:
                    pp.runpp(contingency_net)
                    
                    # Check for violations
                    violations = {
                        'voltage_violations': contingency_net.res_bus[
                            (contingency_net.res_bus.vm_pu < 0.95) | 
                            (contingency_net.res_bus.vm_pu > 1.05)
                        ].index.tolist(),
                        'loading_violations': contingency_net.res_line[
                            contingency_net.res_line.loading_percent > 100
                        ].index.tolist()
                    }
                    
                    results.append({
                        'contingency': f"{element_type}_{idx}",
                        'converged': contingency_net.converged,
                        'violations': violations
                    })
                    
                except Exception as e:
                    results.append({
                        'contingency': f"{element_type}_{idx}",
                        'converged': False,
                        'error': str(e)
                    })
        
        with open(save_file,"w") as f:
            js.dump(
                {
                "status": "success",
                "message": "Contingency analysis completed",
                "results": results
                },
                f
            )
        return f"Contingency analysis completed succesfully and saved to {save_file}"
    except RuntimeError as re:
        return PowerError(
            status="error",
            message=str(re)
        )
    except Exception as e:
        return PowerError(
            status="error",
            message=f"Contingency analysis failed: {str(e)}"
        )

#@power_mcp_tool(mcp)
def get_network_info() -> Dict[str, Any]:
    """Get information about the current network.
    
    Returns:
        Dict containing network statistics and information
    """
    logger.info("Retrieving network information")
    try:
        net = _get_network()
        info = {
            "buses": len(net.bus),
            "lines": len(net.line),
            "trafos": len(net.trafo),
            "generators": len(net.gen),
            "loads": len(net.load),
            "switches": len(net.switch),
 #           "bus_data": net.bus.to_dict(),
 #           "line_data": net.line.to_dict(),
 #           "trafo_data": net.trafo.to_dict()
        }
        
        return {
            "status": "success",
            "message": "Network information retrieved successfully",
            "info": info
        }
    except RuntimeError as re:
        return PowerError(
            status="error",
            message=str(re)
        )
    except Exception as e:
        return PowerError(
            status="error",
            message=f"Failed to get network information: {str(e)}"
        )
@power_mcp_tool(mcp)  
def add_bus(name: str, vn_kv: float, type: str = 'b', zone: Optional[str] = None) -> int:
    """Add a bus to the current network.
    
    Args:
        name: Name of the bus
        vn_kv: Nominal voltage in kV
        type: Type of bus ('b', 'n', 'e')
        zone: Zone of the bus (optional)
        
    Returns:
        Index of the newly created bus
    """
    logger.info(f"Adding bus: {name}")
    try:
        net = _get_network()
        bus_idx = pp.create_bus(net, vn_kv=vn_kv, name=name, type=type, zone=zone)
        return bus_idx
    except RuntimeError as re:
        raise RuntimeError(f"Failed to add bus: {str(re)}")
    except Exception as e:
        raise RuntimeError(f"Failed to add bus: {str(e)}")
    
@power_mcp_tool(mcp)
def add_line(from_bus: int, to_bus: int, length: float, std_type: str, name: Optional[str] = None) -> int:
    """Add a line to the current network. 
    Standards:
    NAYY 4x50 SE

    NAYY 4x120 SE

    NAYY 4x150 SE

    Args:
        from_bus: index of the 'from' bus
        to_bus: index of the 'to' bus
        length: Length of the line in km
        std_type: Standard line type (as defined in pandapower library or custom)
        name: Optional name of the line

    Returns:
        Index of the newly created line
    """
    logger.info(f"Adding line: {name or f'{from_bus}-{to_bus}'} ({std_type}, {length} km)")
    logger.info(f"from_bus {from_bus} to_bus {to_bus} length {length} std_type {std_type} name {name}")
    try:
        net = _get_network()

        # # Allow using bus names instead of indices
        # if isinstance(from_bus, str):
        #     if from_bus not in net.bus.name.values:
        #         raise ValueError(f"Bus '{from_bus}' not found in network.")
        #     from_bus = net.bus.index[net.bus.name == from_bus][0]

        # if isinstance(to_bus, str):
        #     if to_bus not in net.bus.name.values:
        #         raise ValueError(f"Bus '{to_bus}' not found in network.")
        #     to_bus = net.bus.index[net.bus.name == to_bus][0]

        # Create the line
        line_idx = pp.create_line(net, from_bus=from_bus, to_bus=to_bus,
                                  length_km=length, std_type=std_type, name=name)

        return line_idx

    except RuntimeError as re:
        raise RuntimeError(f"Failed to add line: {str(re)}")
    except Exception as e:
        raise RuntimeError(f"Failed to add line: {str(e)}")

@power_mcp_tool(mcp)  
def timeseries(time_steps: int):
    """
    Runs a timeseries on the network

    Args:
        time_steps: Number of time steps
    """
    # load a pandapower network
    #net = mv_oberrhein(scenario='generation')
    # number of time steps
    n_ts = time_steps
    net = _get_network()
    # load your timeseries from a file (here csv file)
    # df = pd.read_csv("sgen_timeseries.csv")
    # or create a DataFrame with some random time series as an example
    df = pd.DataFrame(np.random.normal(1., 0.1, size=(n_ts, len(net.sgen.index))),
                    index=list(range(n_ts)), columns=net.sgen.index) * net.sgen.p_mw.values
    # create the data source from it
    ds = DFData(df)

    # initialising ConstControl controller to update values of the regenerative generators ("sgen" elements)
    # the element_index specifies which elements to update (here all sgens in the net since net.sgen.index is passed)
    # the controlled variable is "p_mw"
    # the profile_name are the columns in the csv file (here this is also equal to the sgen indices 0-N )
    const_sgen = ConstControl(net, element='sgen', element_index=net.sgen.index,
                            variable='p_mw', data_source=ds, profile_name=net.sgen.index)

    # do the same for loads
    # df = pd.read_csv("load_timeseries.csv")
    # create a DataFrame with some random time series as an example
    df = pd.DataFrame(np.random.normal(1., 0.1, size=(n_ts, len(net.load.index))),
                    index=list(range(n_ts)), columns=net.load.index) * net.load.p_mw.values
    ds = DFData(df)
    const_load = ConstControl(net, element='load', element_index=net.load.index,
                            variable='p_mw', data_source=ds, profile_name=net.load.index)

    # starting the timeseries simulation for one day -> 96 15 min values.
    run_timeseries(net)


    
@power_mcp_tool(mcp)
def save_network(file_path: str) -> Dict[str, Any]:
    """Save a pandapower network to a file.
    
    Args:
        file_path: Path to save the network file (.json)
        
    Returns:
        Dict containing status and network information
    """

    logger.info(f"Saving network at: {file_path}")
    global _current_net
    try:
        if file_path.endswith('.json'):
            pp.to_json(_current_net,file_path)
        else:
            raise ValueError("Unsupported file format. Use .json.")
            
        return {
            "status": "success",
            "message": f"Network saved successfully to {file_path}",
            "network_info": {
                "buses": len(_current_net.bus),
                "lines": len(_current_net.line),
                "trafos": len(_current_net.trafo)
            }
        }
    except FileNotFoundError:
        return PowerError(
            status="error",
            message=f"File not found: {file_path}"
        )
    except ValueError as ve:
        return PowerError(
            status="error",
            message=str(ve)
        )
    except Exception as e:
        return PowerError(
            status="error",
            message=f"Failed to save network: {str(e)}"
        )



if __name__ == "__main__":
    mcp.run(transport="stdio") 