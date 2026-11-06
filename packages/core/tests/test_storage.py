import boto3
import pytest
from moto import mock_aws

from fatecorg_core.storage import LocalStorage, S3Settings, S3Storage

CHAVE = "ppcs/pompeia/ads/abc.pdf"


@pytest.fixture
def s3():
    with mock_aws():
        cliente = boto3.client("s3", region_name="us-east-1")
        cliente.create_bucket(Bucket="ppcs")
        settings = S3Settings(_env_file=None, bucket="ppcs")  # type: ignore[call-arg]
        yield S3Storage(settings, cliente=cliente)


def test_s3_guarda_le_e_sabe_se_existe(s3):
    assert not s3.existe(CHAVE)
    s3.guardar(CHAVE, b"%PDF-1.7", "application/pdf")
    assert s3.existe(CHAVE)
    assert s3.ler(CHAVE) == b"%PDF-1.7"
    head = s3.cliente.head_object(Bucket="ppcs", Key=CHAVE)
    assert head["ContentType"] == "application/pdf"


def test_local_guarda_na_mesma_chave(tmp_path):
    local = LocalStorage(tmp_path)
    local.guardar(CHAVE, b"%PDF", "application/pdf")
    assert (tmp_path / CHAVE).read_bytes() == b"%PDF"
    assert local.existe(CHAVE)


def test_local_recusa_chave_fora_da_pasta(tmp_path):
    with pytest.raises(ValueError):
        LocalStorage(tmp_path).guardar("../fora.pdf", b"x", "application/pdf")
