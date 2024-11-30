from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Union, List, Literal
from collections import deque


class PlotData:
    """
        This class is initiated in the BaseExchange.
        Some of essential plots are populated in the exchange class.
        While this is a generic module, it is adviced to use this as <exchange object>.get_plot_data()
    """
    def __init__(self, max_len: int):
        self.data = {}
        self._max_len = max_len

    def set_topic(self, topic: str,
                  color: str,
                  lines_or_markers: Literal['lines', 'markers'],
                  pattern: Literal["circle", "triangle-up", "dashdot", "dash", "dot", "solid"]
                  ) -> None:
        """
        Plot data is grouped under topics.
        Before a plot is recorded, make sure a topic is set.
        You can set more than one plot topics by calling this method multiple times.
        But each topic must have a unique name
        Args:
            topic: Topic of the plot
            color: Color of the plot
            lines_or_markers: 'lines' or 'markers'. The plot type
            pattern: Pattern used to to draw the plot

        Returns:

        """
        # self.data[topic] = {'color': color, 'pattern': pattern, 'time_series': [], 'topic': topic,
        #                     'lines_or_markers': lines_or_markers}
        self.data[topic] = {'color': color, 'pattern': pattern, 'time_series': deque(), 'topic': topic,
                            'lines_or_markers': lines_or_markers}

    def add(self, topic: str, time: datetime, num: Union[int, float], label: str = '') -> None:
        """
        Records time series data for plotting
        Args:
            topic: Plot's topic (What was set using set_topic() )
            time: Time of the datapoint
            num: Datapoint as a numeric value
            label: Label is assigned (optionally) for "marker" type plots. When the mouse hovers, the label is displayed
                    As an example: Makers can be plotted to show order locations. The label can contain information
                                    such as "Order ID, Order type"

        Returns:
            None
        """
        time_series = self.data[topic]['time_series']
        time_series.append([time, num, label])

        if 0 < self._max_len < len(time_series):
            # time_series.pop(0)
            time_series.popleft()

    def get_topics(self) -> list:
        """
        Returns all the topics
        Returns:
            List of orders
        """
        return list(self.data.keys())

    def is_topic_exist(self, topic: str) -> bool:
        """
        Check if a topic is in the plots
        Args:
            topic: plot topic as string

        Returns:
            True if the plot topic exits else False
        """
        return topic in self.data

    def plot_topics(self, plots: List[dict], rows=1, cols=1, length=-1, plot_compressed: bool = False, plot_compressed_size: int = 10000):
        """
        Plot topics on a graph or sub graphs
        Args:
            plots: A list of dicts containing information about subplot.
                    Dict structure is:
                        {
                            'topic': '<Topic of the subplot>',
                            'col': '<Col of the subplot>',
                            'row': '<Row of the subplot>',
                        }
            rows: Number of rows in the graph
            cols: Number of columns in the graph
            length: Length of the winddow from the end,
            plot_compressed: if True, the graph is compressed to "compressed_size".
            plot_compressed_size: The graph resolution in points. Note: (only "lines" mode plots are affected)
        Returns:

        """
        fig = make_subplots(rows=rows, cols=cols)

        for plot in plots:
            if plot['col'] > cols or plot['row'] > rows:
                raise Exception(f'Col number and Row number must be less than rows={rows}, cols={cols}')

            data = self.data[plot['topic']]
            data_time_series = self.data[plot['topic']]['time_series']
            data_len = len(data_time_series)

            oldest_close_price_ranged = None
            oldest_close_price_limit = len(self.data['Candle Close Price']['time_series'])

            if length != -1 and length < oldest_close_price_limit:
                oldest_close_price_ranged = self.data['Candle Close Price']['time_series'][(oldest_close_price_limit - length)]

            if length != -1 and length < data_len:
                data_time_series = data_time_series[(data_len - length): -1]

            if plot_compressed and data['lines_or_markers'] == 'lines':
                data_time_series = self.__compress_graph(data_time_series, plot_compressed, plot_compressed_size)

            trace = self.__topic_to_plotly_trace(topic=plot['topic'],
                                                 time_series=data_time_series,
                                                 lines_or_markers=data['lines_or_markers'],
                                                 oldest_close_price_ranged=oldest_close_price_ranged
                                                 )

            fig.add_trace(trace=trace, col=plot['col'], row=plot['row'])
        return fig

    def __topic_to_plotly_trace(self, topic: dict, time_series: list, lines_or_markers: Literal['lines', 'markers'],
                                oldest_close_price_ranged):
        data = self.data[topic]


        # Filter out all the records that are older than the oldest record of Candle Close Price
        trace_config = {
            'x': [record[0] for record in time_series if oldest_close_price_ranged is None or record[0] > oldest_close_price_ranged[0]],
            'y': [record[1] for record in time_series if oldest_close_price_ranged is None or record[0] > oldest_close_price_ranged[0]],
            'name': topic,
            'mode': lines_or_markers
        }

        if lines_or_markers == 'lines':
            trace_config['line'] = dict(dash=data['pattern'], width=2, color=data['color'])

        if lines_or_markers == 'markers':
            trace_config['marker'] = dict(symbol=data['pattern'], size=8, color=data['color'])
            trace_config['text'] = [record[2] for record in time_series]

        return go.Scatter(**trace_config)

    def __compress_graph(self, data: List, is_compressed: bool = False, compressed_size: int = 10000) -> List:
        data = list(data)
        data_len = len(data)
        comp_skip_size = int(data_len/compressed_size)
        comp_skip_size = 1 if comp_skip_size == 0 else comp_skip_size

        # Compressing data by skipping data points. Note: This always preserves the first data point
        compressed_data = [data_record for idx, data_record in enumerate(data) if idx % comp_skip_size == 0]

        # Allways keep the last element
        if len(data) > 0 and compressed_data[-1] != data[-1]:
            compressed_data.append(data[-1])

        return compressed_data
