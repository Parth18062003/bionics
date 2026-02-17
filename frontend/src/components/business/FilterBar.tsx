import { SegmentedControl } from "../ui/SegmentedControl"
import { Button } from "../ui/Button"
import { X, Filter } from "lucide-react"

export function FilterBar() {
    return (
        <div className="flex flex-col gap-4 border-b border-neutral-200 pb-4 mb-6">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-neutral-500 uppercase tracking-wider text-[11px]">Env</span>
                        <SegmentedControl
                            options={[{ value: 'all', label: 'All' }, { value: 'sandbox', label: 'SBOX' }, { value: 'production', label: 'PROD' }]}
                            value="all"
                            onChange={() => { }}
                            className="bg-neutral-50"
                        />
                    </div>

                    <div className="h-6 w-[1px] bg-neutral-200" />

                    <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-neutral-500 uppercase tracking-wider text-[11px]">Risk</span>
                        <SegmentedControl
                            options={[{ value: 'all', label: 'All' }, { value: 'high', label: 'High+' }]}
                            value="all"
                            onChange={() => { }}
                            className="bg-neutral-50"
                        />
                    </div>
                </div>

                <Button variant="ghost" size="sm" className="text-neutral-500 h-8">
                    <Filter className="w-3 h-3 mr-2" />
                    More Filters
                </Button>
            </div>

            {/* Active Chips Placeholder */}
            {false && (
                <div className="flex gap-2">
                    <div className="inline-flex items-center rounded-full bg-neutral-100 px-2.5 py-0.5 text-xs font-medium text-neutral-800">
                        Env: PRODUCTION
                        <button className="ml-1.5 inline-flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full text-neutral-400 hover:bg-neutral-200 hover:text-neutral-500">
                            <span className="sr-only">Remove large option</span>
                            <X className="h-3 w-3" />
                        </button>
                    </div>
                </div>
            )}
        </div>
    )
}
