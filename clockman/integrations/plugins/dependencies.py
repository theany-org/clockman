"""
Plugin dependency management system for Clockman.

This module provides dependency resolution, validation, and lifecycle
management for plugins with complex interdependencies.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from packaging import version

logger = logging.getLogger(__name__)


class DependencyType(str, Enum):
    """Types of plugin dependencies."""
    REQUIRED = "required"      # Must be present and enabled
    OPTIONAL = "optional"      # Can be present but not required
    CONFLICTS = "conflicts"    # Cannot be present/enabled
    SUGGESTS = "suggests"      # Recommended but not required


@dataclass
class DependencySpec:
    """Specification for a plugin dependency."""
    name: str
    type: DependencyType
    version_constraint: Optional[str] = None  # e.g., ">=1.0.0,<2.0.0"
    description: Optional[str] = None
    
    def matches_version(self, plugin_version: str) -> bool:
        """Check if a plugin version matches this dependency constraint."""
        if not self.version_constraint:
            return True
        
        try:
            return version.check_version(plugin_version, self.version_constraint)
        except Exception as e:
            logger.warning(f"Error checking version constraint '{self.version_constraint}' "
                         f"against '{plugin_version}': {e}")
            return False


@dataclass
class PluginMetadata:
    """Extended metadata for a plugin including dependencies."""
    name: str
    version: str
    description: str = ""
    author: str = ""
    dependencies: List[DependencySpec] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)  # Capabilities this plugin provides
    categories: List[str] = field(default_factory=list)  # Plugin categories
    min_clockman_version: Optional[str] = None
    max_clockman_version: Optional[str] = None
    enabled: bool = True
    
    @classmethod
    def from_plugin_info(cls, plugin_info) -> "PluginMetadata":
        """Create metadata from a plugin's info object."""
        dependencies = []
        
        # Extract dependencies from plugin info if available
        if hasattr(plugin_info, 'dependencies'):
            for dep in plugin_info.dependencies:
                if isinstance(dep, dict):
                    dependencies.append(DependencySpec(
                        name=dep.get('name', ''),
                        type=DependencyType(dep.get('type', DependencyType.REQUIRED)),
                        version_constraint=dep.get('version'),
                        description=dep.get('description')
                    ))
                elif isinstance(dep, str):
                    # Simple string dependency
                    dependencies.append(DependencySpec(
                        name=dep,
                        type=DependencyType.REQUIRED
                    ))
        
        return cls(
            name=plugin_info.name,
            version=plugin_info.version,
            description=plugin_info.description,
            author=getattr(plugin_info, 'author', ''),
            dependencies=dependencies,
            provides=getattr(plugin_info, 'provides', []),
            categories=getattr(plugin_info, 'categories', []),
            min_clockman_version=getattr(plugin_info, 'min_clockman_version', None),
            max_clockman_version=getattr(plugin_info, 'max_clockman_version', None),
        )


@dataclass
class DependencyError:
    """Represents a dependency resolution error."""
    plugin_name: str
    error_type: str
    message: str
    dependency_name: Optional[str] = None


class DependencyResolver:
    """
    Resolves plugin dependencies and determines load order.
    
    This class analyzes plugin dependencies and provides:
    - Dependency validation
    - Load order determination
    - Conflict detection
    - Missing dependency reporting
    """
    
    def __init__(self):
        """Initialize the dependency resolver."""
        self.available_plugins: Dict[str, PluginMetadata] = {}
        self.loaded_plugins: Set[str] = set()
    
    def register_plugin(self, metadata: PluginMetadata) -> None:
        """Register a plugin's metadata for dependency resolution."""
        self.available_plugins[metadata.name] = metadata
        logger.debug(f"Registered plugin metadata for '{metadata.name}'")
    
    def unregister_plugin(self, plugin_name: str) -> None:
        """Unregister a plugin's metadata."""
        if plugin_name in self.available_plugins:
            del self.available_plugins[plugin_name]
            self.loaded_plugins.discard(plugin_name)
            logger.debug(f"Unregistered plugin metadata for '{plugin_name}'")
    
    def mark_loaded(self, plugin_name: str) -> None:
        """Mark a plugin as loaded."""
        self.loaded_plugins.add(plugin_name)
    
    def mark_unloaded(self, plugin_name: str) -> None:
        """Mark a plugin as unloaded."""
        self.loaded_plugins.discard(plugin_name)
    
    def validate_dependencies(self, plugin_name: str) -> List[DependencyError]:
        """
        Validate dependencies for a specific plugin.
        
        Args:
            plugin_name: Name of the plugin to validate
            
        Returns:
            List of dependency errors
        """
        errors = []
        
        if plugin_name not in self.available_plugins:
            errors.append(DependencyError(
                plugin_name=plugin_name,
                error_type="not_found",
                message=f"Plugin '{plugin_name}' not found in available plugins"
            ))
            return errors
        
        plugin_metadata = self.available_plugins[plugin_name]
        
        for dependency in plugin_metadata.dependencies:
            if dependency.type == DependencyType.REQUIRED:
                # Check if required dependency exists and is compatible
                if dependency.name not in self.available_plugins:
                    errors.append(DependencyError(
                        plugin_name=plugin_name,
                        error_type="missing_required",
                        message=f"Required dependency '{dependency.name}' not found",
                        dependency_name=dependency.name
                    ))
                else:
                    dep_metadata = self.available_plugins[dependency.name]
                    if not dependency.matches_version(dep_metadata.version):
                        errors.append(DependencyError(
                            plugin_name=plugin_name,
                            error_type="version_mismatch",
                            message=f"Dependency '{dependency.name}' version {dep_metadata.version} "
                                   f"doesn't match constraint {dependency.version_constraint}",
                            dependency_name=dependency.name
                        ))
            
            elif dependency.type == DependencyType.CONFLICTS:
                # Check for conflicts
                if dependency.name in self.available_plugins:
                    dep_metadata = self.available_plugins[dependency.name]
                    if dep_metadata.enabled and dependency.matches_version(dep_metadata.version):
                        errors.append(DependencyError(
                            plugin_name=plugin_name,
                            error_type="conflict",
                            message=f"Plugin conflicts with '{dependency.name}' version {dep_metadata.version}",
                            dependency_name=dependency.name
                        ))
        
        return errors
    
    def resolve_load_order(self, plugin_names: List[str]) -> Tuple[List[str], List[DependencyError]]:
        """
        Resolve the correct load order for a set of plugins.
        
        Args:
            plugin_names: Names of plugins to load
            
        Returns:
            Tuple of (ordered_plugin_names, dependency_errors)
        """
        errors = []
        dependency_graph = {}
        
        # Validate all plugins first
        for plugin_name in plugin_names:
            plugin_errors = self.validate_dependencies(plugin_name)
            errors.extend(plugin_errors)
            
            if plugin_name in self.available_plugins:
                dependency_graph[plugin_name] = []
                plugin_metadata = self.available_plugins[plugin_name]
                
                for dependency in plugin_metadata.dependencies:
                    if dependency.type == DependencyType.REQUIRED and dependency.name in plugin_names:
                        dependency_graph[plugin_name].append(dependency.name)
        
        # If there are critical errors, return empty order
        critical_errors = [e for e in errors if e.error_type in ["not_found", "missing_required", "conflict"]]
        if critical_errors:
            return [], errors
        
        # Perform topological sort
        try:
            ordered_plugins = self._topological_sort(dependency_graph)
            return ordered_plugins, errors
        except ValueError as e:
            errors.append(DependencyError(
                plugin_name="system",
                error_type="circular_dependency",
                message=str(e)
            ))
            return [], errors
    
    def _topological_sort(self, dependency_graph: Dict[str, List[str]]) -> List[str]:
        """
        Perform topological sort on dependency graph.
        
        Args:
            dependency_graph: Dict mapping plugin names to their dependencies
            
        Returns:
            List of plugin names in dependency order
            
        Raises:
            ValueError: If circular dependencies are detected
        """
        # Kahn's algorithm for topological sorting
        in_degree = {node: 0 for node in dependency_graph}
        
        # Calculate in-degrees
        for node, dependencies in dependency_graph.items():
            for dependency in dependencies:
                if dependency in in_degree:
                    in_degree[node] += 1
        
        # Find nodes with no dependencies
        queue = [node for node, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            current = queue.pop(0)
            result.append(current)
            
            # Update in-degrees of dependent nodes
            for node, dependencies in dependency_graph.items():
                if current in dependencies:
                    in_degree[node] -= 1
                    if in_degree[node] == 0:
                        queue.append(node)
        
        # Check for circular dependencies
        if len(result) != len(dependency_graph):
            remaining_nodes = set(dependency_graph.keys()) - set(result)
            raise ValueError(f"Circular dependency detected among plugins: {remaining_nodes}")
        
        return result
    
    def get_plugin_dependents(self, plugin_name: str) -> List[str]:
        """
        Get list of plugins that depend on the given plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            List of dependent plugin names
        """
        dependents = []
        
        for name, metadata in self.available_plugins.items():
            for dependency in metadata.dependencies:
                if (dependency.name == plugin_name and 
                    dependency.type == DependencyType.REQUIRED):
                    dependents.append(name)
        
        return dependents
    
    def can_unload_plugin(self, plugin_name: str) -> Tuple[bool, List[str]]:
        """
        Check if a plugin can be safely unloaded.
        
        Args:
            plugin_name: Name of the plugin to check
            
        Returns:
            Tuple of (can_unload, blocking_plugins)
        """
        if plugin_name not in self.loaded_plugins:
            return True, []
        
        blocking_plugins = []
        
        for dependent in self.get_plugin_dependents(plugin_name):
            if dependent in self.loaded_plugins:
                blocking_plugins.append(dependent)
        
        return len(blocking_plugins) == 0, blocking_plugins
    
    def suggest_load_order_for_plugin(self, plugin_name: str) -> Tuple[List[str], List[DependencyError]]:
        """
        Suggest the complete load order needed to load a specific plugin.
        
        Args:
            plugin_name: Name of the plugin to load
            
        Returns:
            Tuple of (suggested_load_order, errors)
        """
        if plugin_name not in self.available_plugins:
            return [], [DependencyError(
                plugin_name=plugin_name,
                error_type="not_found",
                message=f"Plugin '{plugin_name}' not found"
            )]
        
        # Collect all required dependencies recursively
        all_plugins = set()
        
        def collect_dependencies(name: str, visited: Set[str]) -> None:
            if name in visited:
                return
            visited.add(name)
            
            if name in self.available_plugins:
                all_plugins.add(name)
                metadata = self.available_plugins[name]
                
                for dependency in metadata.dependencies:
                    if dependency.type == DependencyType.REQUIRED:
                        collect_dependencies(dependency.name, visited)
        
        collect_dependencies(plugin_name, set())
        
        return self.resolve_load_order(list(all_plugins))
    
    def get_dependency_tree(self, plugin_name: str, max_depth: int = 5) -> Dict[str, Any]:
        """
        Get the dependency tree for a plugin.
        
        Args:
            plugin_name: Name of the plugin
            max_depth: Maximum recursion depth
            
        Returns:
            Nested dictionary representing the dependency tree
        """
        def build_tree(name: str, depth: int) -> Dict[str, Any]:
            if depth >= max_depth or name not in self.available_plugins:
                return {"name": name, "available": name in self.available_plugins}
            
            metadata = self.available_plugins[name]
            tree = {
                "name": name,
                "version": metadata.version,
                "available": True,
                "loaded": name in self.loaded_plugins,
                "dependencies": []
            }
            
            for dependency in metadata.dependencies:
                if dependency.type in [DependencyType.REQUIRED, DependencyType.OPTIONAL]:
                    dep_tree = build_tree(dependency.name, depth + 1)
                    dep_tree["type"] = dependency.type.value
                    dep_tree["version_constraint"] = dependency.version_constraint
                    tree["dependencies"].append(dep_tree)
            
            return tree
        
        return build_tree(plugin_name, 0)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get dependency resolver statistics."""
        total_dependencies = sum(
            len(metadata.dependencies) 
            for metadata in self.available_plugins.values()
        )
        
        required_deps = sum(
            sum(1 for dep in metadata.dependencies if dep.type == DependencyType.REQUIRED)
            for metadata in self.available_plugins.values()
        )
        
        conflicts = sum(
            sum(1 for dep in metadata.dependencies if dep.type == DependencyType.CONFLICTS)
            for metadata in self.available_plugins.values()
        )
        
        return {
            "total_plugins": len(self.available_plugins),
            "loaded_plugins": len(self.loaded_plugins),
            "total_dependencies": total_dependencies,
            "required_dependencies": required_deps,
            "conflicts": conflicts,
            "plugins_with_dependencies": sum(
                1 for metadata in self.available_plugins.values()
                if metadata.dependencies
            ),
        }


# Global dependency resolver instance
_dependency_resolver: Optional[DependencyResolver] = None


def get_dependency_resolver() -> DependencyResolver:
    """Get the global dependency resolver instance."""
    global _dependency_resolver
    if _dependency_resolver is None:
        _dependency_resolver = DependencyResolver()
    return _dependency_resolver