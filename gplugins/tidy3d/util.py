def sort_layers(layers, sort_by, reverse=False):
    return dict(
        sorted(layers.items(), key=lambda x: getattr(x[1], sort_by), reverse=reverse)
    )
