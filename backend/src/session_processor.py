#!/usr/bin/env python3
"""
Polar Session Processor

Processes Polar training session JSON files, filters relevant sessions,
and extracts important metrics to CSV format.
"""

import json
import csv
import glob
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import os

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    # Fallback progress indicator
    class tqdm:
        def __init__(self, iterable, **kwargs):
            self.iterable = iterable
            self.desc = kwargs.get('desc', 'Processing')
            self.total = len(iterable) if hasattr(iterable, '__len__') else None
            self.count = 0
            
        def __iter__(self):
            for item in self.iterable:
                yield item
                self.count += 1
                if self.total and self.count % max(1, self.total // 20) == 0:
                    percent = (self.count / self.total) * 100
                    print(f"\r{self.desc}: {self.count}/{self.total} ({percent:.1f}%)", end='', flush=True)
            if self.total:
                print(f"\r{self.desc}: {self.total}/{self.total} (100.0%)")
            print()  # New line


class SessionProcessor:
    """Processes Polar training session files."""
    
    def __init__(self, sessions_dir: str = "sessions"):
        self.sessions_dir = Path(sessions_dir)
        self.processed_sessions = []
        
    def load_session(self, filepath: Path) -> Optional[Dict]:
        """Load a single session JSON file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Warning: Could not load {filepath}: {e}")
            return None
    
    def should_include_session(self, session: Dict, filters: Dict) -> bool:
        """Determine if a session meets the filtering criteria."""
        # Date range filter
        if 'start_date' in filters or 'end_date' in filters:
            start_time = datetime.fromisoformat(session['startTime'].replace('Z', '+00:00'))
            if 'start_date' in filters:
                if start_time < datetime.fromisoformat(filters['start_date']):
                    return False
            if 'end_date' in filters:
                if start_time > datetime.fromisoformat(filters['end_date']):
                    return False
        
        # Sport type filter
        if 'sports' in filters:
            session_sports = [exercise.get('sport') for exercise in session.get('exercises', [])]
            if not any(sport in filters['sports'] for sport in session_sports):
                return False
        
        # Duration filter (in seconds)
        if 'min_duration' in filters:
            duration_str = session.get('duration', 'PT0S')
            duration_seconds = self.parse_duration(duration_str)
            if duration_seconds < filters['min_duration']:
                return False
        
        # Distance filter (in meters)
        if 'min_distance' in filters:
            distance = session.get('distance', 0)
            if distance < filters['min_distance']:
                return False
        
        # Calories filter
        if 'min_calories' in filters:
            calories = session.get('kiloCalories', 0)
            if calories < filters['min_calories']:
                return False
        
        return True
    
    def parse_duration(self, duration_str: str) -> int:
        """Parse ISO 8601 duration string to seconds."""
        if not duration_str.startswith('PT'):
            return 0
        
        duration_str = duration_str[2:]  # Remove 'PT'
        total_seconds = 0
        
        if 'H' in duration_str:
            hours, duration_str = duration_str.split('H', 1)
            total_seconds += int(hours) * 3600
        
        if 'M' in duration_str:
            minutes, duration_str = duration_str.split('M', 1)
            total_seconds += int(minutes) * 60
        
        if 'S' in duration_str:
            seconds = duration_str.rstrip('S')
            total_seconds += float(seconds)
        
        return int(total_seconds)
    
    def extract_metrics(self, session: Dict) -> Dict:
        """Extract only startTime and autolaps durations from a session."""
        metrics = {}
        
        # Extract start time
        metrics['start_time'] = session.get('startTime', '')
        
        # Extract autolaps durations from all exercises
        autolap_durations = []
        exercises = session.get('exercises', [])
        
        for exercise in exercises:
            autolaps = exercise.get('autoLaps', [])
            for autolap in autolaps:
                duration_str = autolap.get('duration', '')
                if duration_str:
                    # Convert to seconds for easier processing
                    duration_seconds = self.parse_duration(duration_str)
                    autolap_durations.append(duration_seconds)
        
        # Convert seconds to time format using timedelta
        formatted_durations = [str(timedelta(seconds=seconds)) for seconds in autolap_durations]
        
        # Store durations as semicolon-delimited string for CSV compatibility
        metrics['autolap_durations'] = ';'.join(formatted_durations) if formatted_durations else ''
        
        return metrics
    
    def process_sessions(self, filters: Dict = None, output_file: str = "chart_data.json"):
        """Process all sessions matching the filters and export to Chart.js JSON."""
        if filters is None:
            filters = {}
        
        session_files = list(self.sessions_dir.glob("*.json"))
        print(f"Found {len(session_files)} session files")
        
        processed_count = 0
        skipped_count = 0
        
        # Create progress bar
        progress_desc = "Processing sessions"
        if HAS_TQDM:
            session_iterator = tqdm(session_files, desc=progress_desc, unit="files")
        else:
            session_iterator = tqdm(session_files, desc=progress_desc)
        
        for session_file in session_iterator:
            self._current_filename = session_file.name
            session_data = self.load_session(session_file)
            
            if session_data is None:
                skipped_count += 1
                continue
            
            if self.should_include_session(session_data, filters):
                metrics = self.extract_metrics(session_data)
                # Store original session data for metadata extraction
                metrics['exercises'] = session_data.get('exercises', [])
                self.processed_sessions.append(metrics)
                processed_count += 1
                
                # Update progress bar description with current stats
                if HAS_TQDM:
                    session_iterator.set_postfix({
                        'processed': processed_count,
                        'skipped': skipped_count
                    })
            else:
                skipped_count += 1
        
        if self.processed_sessions:
            # Sort by start_time before exporting
            self.processed_sessions.sort(key=lambda x: x.get('start_time', ''))
            
            self.export_to_chartjs(output_file)
    
    def export_to_chartjs(self, output_file: str):
        """Export processed sessions to Chart.js line chart format."""
        if not self.processed_sessions:
            return
        
        import json
        from datetime import datetime
        
        # Prepare datasets for line chart
        datasets = []
        
        for session in self.processed_sessions:
            # Skip sessions without autolaps
            if not session.get('autolap_durations'):
                continue
                
            start_time = session.get('start_time', '')
            
            # Parse autolap durations (they're already in time format)
            duration_strings = session['autolap_durations'].split(';')
            
            # Convert time format back to seconds for Chart.js (it expects numbers)
            lap_times_seconds = []
            for time_str in duration_strings:
                try:
                    # Parse time format like "0:05:39" back to seconds
                    parts = time_str.split(':')
                    if len(parts) == 3:
                        hours, minutes, seconds = map(int, parts)
                        total_seconds = hours * 3600 + minutes * 60 + seconds
                        lap_times_seconds.append(total_seconds)
                except:
                    continue
            
            if not lap_times_seconds:
                continue
                
            # Create dataset for this session
            try:
                session_date = datetime.fromisoformat(start_time.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                label = f"Session {session_date}"
            except:
                label = f"Session {start_time[:10]}"
            
            # Create data points (lap number, lap time in seconds)
            data_points = []
            for i, lap_time in enumerate(lap_times_seconds, 1):
                data_points.append({'x': i, 'y': lap_time})
            
            # Extract metadata from exercises
            meta = {}
            if session.get('exercises'):
                exercise = session['exercises'][0]  # Get first exercise
                meta = {
                    'distance': int(exercise.get('distance', 0)),
                    'duration': self.parse_duration(exercise.get('duration', 'PT0S')),
                    'sport': exercise.get('sport', 'Unknown'),
                    'ascent': int(exercise.get('ascent', 0))
                }
            
            datasets.append({
                'label': label,
                'data': data_points,
                'borderColor': f'rgb({hash(label) % 200 + 50}, {(hash(label) * 2) % 200 + 50}, {(hash(label) * 3) % 200 + 50})',
                'backgroundColor': f'rgba({hash(label) % 200 + 50}, {(hash(label) * 2) % 200 + 50}, {(hash(label) * 3) % 200 + 50}, 0.1)',
                'fill': False,
                'tension': 0.1,
                'meta': meta  # Add metadata for frontend display
            })
        
        # Create Chart.js configuration
        chart_config = {
            'type': 'line',
            'data': {
                'datasets': datasets
            },
            'options': {
                'responsive': True,
                'plugins': {
                    'title': {
                        'display': True,
                        'text': 'Autolap Times by Session'
                    },
                    'legend': {
                        'display': False  # Disabled - using custom legend instead
                    }
                },
                'scales': {
                    'x': {
                        'type': 'linear',
                        'display': True,
                        'title': {
                            'display': True,
                            'text': 'Lap Number'
                        }
                    },
                    'y': {
                        'display': True,
                        'title': {
                            'display': True,
                            'text': 'Lap Time (seconds)'
                        }
                    }
                }
            }
        }
        
        # Write JSON file
        with open(output_file, 'w', encoding='utf-8') as jsonfile:
            json.dump(chart_config, jsonfile, indent=2)
        
        # Auto-register this chart
        self.register_chart(output_file, datasets)
    
    def register_chart(self, output_file: str, datasets: List[Dict]):
        """Register chart in charts.json configuration file."""
        charts_config_path = os.path.join(os.path.dirname(output_file), 'charts.json')
        
        # Load existing charts config or create new one
        if os.path.exists(charts_config_path):
            with open(charts_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {"default": "all", "charts": []}
        
        # Extract metadata from datasets
        sports = list(set([d.get('meta', {}).get('sport', 'Unknown') for d in datasets if d.get('meta')]))
        distances = [d.get('meta', {}).get('distance', 0) for d in datasets if d.get('meta', {}).get('distance', 0) > 0]
        
        # Create chart metadata
        chart_filename = os.path.basename(output_file)
        chart_id = chart_filename.replace('.json', '')
        
        # Generate name and tags based on filename
        name = chart_id.replace('_', ' ').replace('-', ' ').title()
        tags = []
        
        if 'run' in chart_id.lower():
            tags.extend(['running', 'endurance'])
        if 'trail' in chart_id.lower():
            tags.extend(['trail', 'outdoor'])
        if 'km' in chart_id.lower():
            tags.append('distance')
        if chart_id == 'all':
            tags.extend(['comprehensive', 'overview'])
        
        # Add sport-based tags
        for sport in sports:
            if sport.lower() != 'unknown':
                tags.append(sport.lower())
        
        chart_entry = {
            "id": chart_id,
            "file": chart_filename,
            "name": name,
            "description": f"Training sessions: {', '.join(sports) if sports else 'Mixed sports'}",
            "icon": "🏃" if any('run' in s.lower() for s in sports) else "📊",
            "tags": list(set(tags)),  # Remove duplicates
            "metadata": {
                "sessionCount": len(datasets),
                "dateRange": {
                    "start": datasets[0]['label'].split()[-1] if datasets else None,
                    "end": datasets[-1]['label'].split()[-1] if datasets else None
                },
                "sports": sports,
                "distanceRange": {
                    "min": min(distances) if distances else 0,
                    "max": max(distances) if distances else 0
                }
            },
            "lastUpdated": datetime.now().isoformat() + 'Z'
        }
        
        # Update or add chart entry
        existing_index = None
        for i, chart in enumerate(config['charts']):
            if chart['id'] == chart_id:
                existing_index = i
                break
        
        if existing_index is not None:
            config['charts'][existing_index] = chart_entry
        else:
            config['charts'].append(chart_entry)
        
        # Write updated config
        with open(charts_config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)


def main():
    """Main function with command line interface."""
    parser = argparse.ArgumentParser(description='Process Polar training sessions')
    parser.add_argument('--sessions-dir', default='sessions', help='Directory containing session JSON files')
    parser.add_argument('--output', default='chart_data.json', help='Output Chart.js JSON file')
    parser.add_argument('--sport', action='append', help='Filter by sport type (can be used multiple times)')
    parser.add_argument('--start-date', help='Start date filter (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='End date filter (YYYY-MM-DD)')
    parser.add_argument('--min-duration', type=int, help='Minimum duration in seconds')
    parser.add_argument('--min-distance', type=float, help='Minimum distance in meters')
    parser.add_argument('--min-calories', type=int, help='Minimum calories burned')
    
    args = parser.parse_args()
    
    # Build filters dictionary
    filters = {}
    if args.sport:
        filters['sports'] = args.sport
    if args.start_date:
        filters['start_date'] = args.start_date + 'T00:00:00'
    if args.end_date:
        filters['end_date'] = args.end_date + 'T23:59:59'
    if args.min_duration:
        filters['min_duration'] = args.min_duration
    if args.min_distance:
        filters['min_distance'] = args.min_distance
    if args.min_calories:
        filters['min_calories'] = args.min_calories
    
    # Process sessions
    processor = SessionProcessor(args.sessions_dir)
    processor.process_sessions(filters, args.output)


if __name__ == "__main__":
    main()
