import { Card, CardBody, Badge } from './ui'

export function StatCard({ title, value, subtitle, icon: Icon, trend, variant = 'default' }) {
  const variants = {
    default: 'border-slate-800',
    accent: 'border-accent/30 bg-accent/5',
    success: 'border-teal/30 bg-teal/5',
    warning: 'border-amber/30 bg-amber/5',
    danger: 'border-danger/30 bg-danger/5',
  }

  return (
    <Card className={variants[variant]}>
      <CardBody className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{title}</p>
            <p className="text-2xl font-bold text-slate-100 mt-2">{value}</p>
            {subtitle && (
              <p className="text-sm text-slate-400 mt-1">{subtitle}</p>
            )}
            {trend && (
              <p className={`text-xs mt-2 ${trend > 0 ? 'text-teal' : 'text-danger'}`}>
                {trend > 0 ? '↑' : '↓'} {Math.abs(trend)}%
              </p>
            )}
          </div>
          {Icon && (
            <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center">
              <Icon className="w-5 h-5 text-slate-400" />
            </div>
          )}
        </div>
      </CardBody>
    </Card>
  )
}
