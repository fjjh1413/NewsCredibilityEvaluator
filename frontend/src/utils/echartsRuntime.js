import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'


let registered = false

export function getEchartsRuntime() {
  if (!registered) {
    echarts.use([
      BarChart,
      LineChart,
      PieChart,
      GridComponent,
      LegendComponent,
      TooltipComponent,
      CanvasRenderer
    ])
    registered = true
  }

  return echarts
}
