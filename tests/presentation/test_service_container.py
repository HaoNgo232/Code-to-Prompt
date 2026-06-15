from presentation.service_container import ServiceContainer


def test_service_container_init():
    container = ServiceContainer()
    assert container.prompt_builder is not None
